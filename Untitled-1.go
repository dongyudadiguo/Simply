以下是服务器代码:
package main

import (
	"crypto/rand"
	"crypto/sha256"
	"encoding/gob"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"os"
	"sort"
	"strings"
	"sync"
)

type Hash [32]byte
type Identity [32]byte

type UserKey struct {
	User Identity
	Key  Hash
}

type Edge struct {
	Parent Hash
	Child  Hash
}

type VoteKey struct {
	User   Identity
	Parent Hash
	Child  Hash
}

type DB struct {
	Files map[Hash][]byte
	Graph map[Hash][]Hash
	Users map[Identity]bool
	Vals  map[UserKey]Hash
	Score map[Edge]int64
	Voted map[VoteKey]bool
	Seq   map[Edge]int64
	Next  int64
}

type App struct {
	mu     sync.Mutex
	dbFile string
	secret string
	db     DB
}

type Resp struct {
	OK    bool `json:"ok"`
	Error string `json:"error,omitempty"`
	Data  any `json:"data,omitempty"`
}

func newDB() DB {
	return DB{
		Files: map[Hash][]byte{},
		Graph: map[Hash][]Hash{},
		Users: map[Identity]bool{},
		Vals:  map[UserKey]Hash{},
		Score: map[Edge]int64{},
		Voted: map[VoteKey]bool{},
		Seq:   map[Edge]int64{},
	}
}

func (a *App) load() {
	a.db = newDB()

	f, err := os.Open(a.dbFile)
	if err != nil {
		return
	}
	defer f.Close()

	_ = gob.NewDecoder(f).Decode(&a.db)

	if a.db.Files == nil {
		a.db.Files = map[Hash][]byte{}
	}
	if a.db.Graph == nil {
		a.db.Graph = map[Hash][]Hash{}
	}
	if a.db.Users == nil {
		a.db.Users = map[Identity]bool{}
	}
	if a.db.Vals == nil {
		a.db.Vals = map[UserKey]Hash{}
	}
	if a.db.Score == nil {
		a.db.Score = map[Edge]int64{}
	}
	if a.db.Voted == nil {
		a.db.Voted = map[VoteKey]bool{}
	}
	if a.db.Seq == nil {
		a.db.Seq = map[Edge]int64{}
	}
}

func (a *App) save() {
	tmp := a.dbFile + ".tmp"

	f, err := os.Create(tmp)
	if err != nil {
		return
	}

	err = gob.NewEncoder(f).Encode(a.db)
	cerr := f.Close()

	if err == nil && cerr == nil {
		_ = os.Rename(tmp, a.dbFile)
	}
}

func parseHash(s string) (Hash, error) {
	b, err := hex.DecodeString(strings.TrimSpace(s))
	if err != nil || len(b) != 32 {
		return Hash{}, errors.New("bad hex32")
	}

	var h Hash
	copy(h[:], b)
	return h, nil
}

func pathArgs(r *http.Request, prefix string, n int) ([]Hash, bool) {
	s, ok := strings.CutPrefix(r.URL.Path, prefix)
	if !ok {
		return nil, false
	}

	ps := strings.Split(s, "/")
	if len(ps) != n {
		return nil, false
	}

	out := make([]Hash, n)
	for i, p := range ps {
		h, err := parseHash(p)
		if err != nil {
			return nil, false
		}
		out[i] = h
	}

	return out, true
}

func hasChild(xs []Hash, h Hash) bool {
	for _, x := range xs {
		if x == h {
			return true
		}
	}
	return false
}

func (a *App) sortedChildren(parent Hash) []Hash {
	out := append([]Hash(nil), a.db.Graph[parent]...)

	sort.SliceStable(out, func(i, j int) bool {
		ei := Edge{parent, out[i]}
		ej := Edge{parent, out[j]}

		if a.db.Score[ei] != a.db.Score[ej] {
			return a.db.Score[ei] > a.db.Score[ej]
		}

		return a.db.Seq[ei] > a.db.Seq[ej]
	})

	return out
}

func (a *App) verifyTurnstile(token string) bool {
	if a.secret == "" {
		return true
	}

	form := url.Values{
		"secret":   {a.secret},
		"response": {token},
	}

	resp, err := http.PostForm(
		"https://challenges.cloudflare.com/turnstile/v0/siteverify",
		form,
	)
	if err != nil {
		return false
	}
	defer resp.Body.Close()

	var out struct {
		Success bool `json:"success"`
	}

	_ = json.NewDecoder(resp.Body).Decode(&out)
	return out.Success
}

func writeJSON(w http.ResponseWriter, status int, v any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(v)
}

func ok(w http.ResponseWriter, data any) {
	writeJSON(w, http.StatusOK, Resp{
		OK:   true,
		Data: data,
	})
}

func fail(w http.ResponseWriter, status int, msg string) {
	writeJSON(w, status, Resp{
		Error: msg,
	})
}

func only(method string, h http.HandlerFunc) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		if r.Method != method {
			fail(w, http.StatusMethodNotAllowed, method+" only")
			return
		}
		h(w, r)
	}
}

func withArgs(
	method string,
	prefix string,
	n int,
	h func(http.ResponseWriter, *http.Request, []Hash),
) http.HandlerFunc {
	return only(method, func(w http.ResponseWriter, r *http.Request) {
		args, ok := pathArgs(r, prefix, n)
		if !ok {
			fail(w, http.StatusBadRequest, "bad path")
			return
		}
		h(w, r, args)
	})
}

func cors(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Access-Control-Allow-Origin", "*")
		w.Header().Set("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
		w.Header().Set("Access-Control-Allow-Headers", "Content-Type")

		if r.Method == http.MethodOptions {
			w.WriteHeader(http.StatusNoContent)
			return
		}

		next.ServeHTTP(w, r)
	})
}

func (a *App) register(w http.ResponseWriter, r *http.Request) {
	var req struct {
		Token string `json:"token"`
	}

	_ = json.NewDecoder(r.Body).Decode(&req)

	if !a.verifyTurnstile(req.Token) {
		fail(w, http.StatusForbidden, "invalid token")
		return
	}

	var id Identity
	if _, err := rand.Read(id[:]); err != nil {
		fail(w, http.StatusInternalServerError, "random failed")
		return
	}

	a.mu.Lock()
	a.db.Users[id] = true
	a.save()
	a.mu.Unlock()

	ok(w, map[string]string{
		"id": hex.EncodeToString(id[:]),
	})
}

func (a *App) upload(w http.ResponseWriter, r *http.Request) {
	raw, err := io.ReadAll(r.Body)
	if err != nil || len(raw) == 0 {
		fail(w, http.StatusBadRequest, "empty")
		return
	}

	h := sha256.Sum256(raw)

	a.mu.Lock()
	if _, exists := a.db.Files[h]; !exists {
		a.db.Files[h] = raw
		a.save()
	}
	a.mu.Unlock()

	ok(w, map[string]string{
		"hash": hex.EncodeToString(h[:]),
	})
}

func (a *App) download(w http.ResponseWriter, r *http.Request, ps []Hash) {
	h := ps[0]

	a.mu.Lock()
	raw, found := a.db.Files[h]
	a.mu.Unlock()

	if !found {
		fail(w, http.StatusNotFound, "not found")
		return
	}

	w.Header().Set("Content-Type", "application/octet-stream")
	w.Header().Set("Content-Length", fmt.Sprint(len(raw)))
	_, _ = w.Write(raw)
}

func (a *App) addEdge(w http.ResponseWriter, r *http.Request, ps []Hash) {
	parent, child := ps[0], ps[1]

	a.mu.Lock()
	if !hasChild(a.db.Graph[parent], child) {
		a.db.Graph[parent] = append(a.db.Graph[parent], child)
		a.save()
	}
	a.mu.Unlock()

	ok(w, nil)
}

func (a *App) children(w http.ResponseWriter, r *http.Request, ps []Hash) {
	parent := ps[0]

	type Child struct {
		Hash  string `json:"hash"`
		Score int64  `json:"score"`
	}

	a.mu.Lock()

	list := a.sortedChildren(parent)
	out := make([]Child, 0, len(list))

	for _, child := range list {
		e := Edge{parent, child}
		out = append(out, Child{
			Hash:  hex.EncodeToString(child[:]),
			Score: a.db.Score[e],
		})
	}

	a.mu.Unlock()

	ok(w, map[string]any{
		"children": out,
	})
}

func (a *App) vote(w http.ResponseWriter, r *http.Request, ps []Hash) {
	user := Identity(ps[0])
	parent, child := ps[1], ps[2]

	a.mu.Lock()
	defer a.mu.Unlock()

	if !a.db.Users[user] {
		fail(w, http.StatusForbidden, "unregistered")
		return
	}

	if !hasChild(a.db.Graph[parent], child) {
		fail(w, http.StatusBadRequest, "no edge")
		return
	}

	vk := VoteKey{user, parent, child}
	e := Edge{parent, child}

	if !a.db.Voted[vk] {
		a.db.Voted[vk] = true
		a.db.Score[e]++
	}

	a.db.Next++
	a.db.Seq[e] = a.db.Next

	a.save()
	ok(w, nil)
}

func (a *App) userSet(w http.ResponseWriter, r *http.Request, ps []Hash) {
	user := Identity(ps[0])
	key, value := ps[1], ps[2]

	a.mu.Lock()
	defer a.mu.Unlock()

	if !a.db.Users[user] {
		fail(w, http.StatusForbidden, "unregistered")
		return
	}

	a.db.Vals[UserKey{user, key}] = value
	a.save()

	ok(w, nil)
}

func (a *App) userGet(w http.ResponseWriter, r *http.Request, ps []Hash) {
	user := Identity(ps[0])
	key := ps[1]

	a.mu.Lock()
	defer a.mu.Unlock()

	if !a.db.Users[user] {
		fail(w, http.StatusForbidden, "unregistered")
		return
	}

	value, found := a.db.Vals[UserKey{user, key}]
	if !found {
		fail(w, http.StatusNotFound, "not set")
		return
	}

	ok(w, map[string]string{
		"value": hex.EncodeToString(value[:]),
	})
}

func main() {
	app := &App{
		dbFile: "cvm.gob",
		secret: os.Getenv("CF_TURNSTILE_SECRET"),
	}

	app.load()

	mux := http.NewServeMux()

	mux.HandleFunc("/", func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != "/" {
			http.NotFound(w, r)
			return
		}
		http.ServeFile(w, r, "index.html")
	})

	mux.HandleFunc("/api/register", only("POST", app.register))
	mux.HandleFunc("/api/upload", only("POST", app.upload))
	mux.HandleFunc("/api/file/", withArgs("GET", "/api/file/", 1, app.download))
	mux.HandleFunc("/api/edge/", withArgs("POST", "/api/edge/", 2, app.addEdge))
	mux.HandleFunc("/api/children/", withArgs("GET", "/api/children/", 1, app.children))
	mux.HandleFunc("/api/vote/", withArgs("POST", "/api/vote/", 3, app.vote))
	mux.HandleFunc("/api/user/set/", withArgs("POST", "/api/user/set/", 3, app.userSet))
	mux.HandleFunc("/api/user/get/", withArgs("GET", "/api/user/get/", 2, app.userGet))

	fmt.Println("http://localhost:9000")
    panic(http.ListenAndServe(":9000", cors(mux)))
}

以下是这个服务器的持久服务文件
[Service]
WorkingDirectory=/home/ubuntu/oneserver
ExecStart=/home/ubuntu/oneserver/oneserver
Environment=CF_TURNSTILE_SECRET=0x4AAAAAADNgS5W8tZBxH7QXNH_QwbAeWi4

以下是这个服务器的常用指令
sudo systemctl start oneserver

sudo cp /home/ubuntu/oneserver.service /etc/systemd/system/oneserver.service
sudo systemctl daemon-reload

cd /home/ubuntu/oneserver/
go build -o oneserver main.go
sudo systemctl restart oneserver
sudo systemctl status oneserver --no-pager

sudo systemctl stop oneserver
sudo systemctl start oneserver

以下是虚拟机代码

<script>
const host = "124.221.146.23";
const port = 9000;
const apiBase = `http://${host}:${port}`;

const textDecoder = new TextDecoder();

const CVM = globalThis.CVM = {
  PTR: null,
  IMP: null,
};

const toHex = (bytes) =>
  [...bytes].map((byte) => byte.toString(16).padStart(2, "0")).join("");

const fromHex = (hex) =>
  new Uint8Array(hex.match(/../g).map((x) => parseInt(x, 16)));

const downloadFile = async (hash) =>
  new Uint8Array(
    await (await fetch(`${apiBase}/api/file/${toHex(hash)}`)).arrayBuffer()
  );

const getfirstchild = async (parent) => {
  const res = await fetch(`${apiBase}/api/children/${toHex(parent)}`);
  const json = await res.json();

  if (!json.ok || !json.data.children.length) {
    throw new Error("no child");
  }

  return fromHex(json.data.children[0].hash);
};

Object.assign(CVM, {
  hex: toHex,
  download_file: downloadFile,
  getfirstchild,
});

(async () => {
  const startFileData = await downloadFile(
    await getfirstchild(new Uint8Array(32))
  );

  CVM.PTR = {
    buf: startFileData,
    off: 0,
  };

  const javaScriptHash = startFileData.subarray(0, 32);
  const javaScriptSource = textDecoder.decode(
    await downloadFile(await getfirstchild(javaScriptHash))
  );

  CVM.IMP = () => eval(`(async()=>{${javaScriptSource}})()`);
  await CVM.IMP();
})();
</script>

以下是标准持续函数

// ============================================================
// 标准持续函数
// ============================================================
(() => {
  const cvm = globalThis.CVM;
  const API = typeof apiBase !== "undefined"
    ? apiBase
    : globalThis.apiBase || location.origin;

  const enc = new TextEncoder(), dec = new TextDecoder();
  const ZERO = new Uint8Array(32);

  const bytes = (x) => x instanceof Uint8Array ? x :
    x instanceof ArrayBuffer ? new Uint8Array(x) :
    ArrayBuffer.isView(x) ? new Uint8Array(x.buffer, x.byteOffset, x.byteLength) :
    enc.encode(String(x ?? ""));

  const hex = (x) => typeof x === "string" ? x.trim().toLowerCase() :
    [...bytes(x)].map((b) => b.toString(16).padStart(2, "0")).join("");

  const unhex = (h) => {
    h = hex(h);
    if (!/^[0-9a-f]*$/.test(h) || h.length % 2) throw new Error("bad hex");
    return new Uint8Array(h.match(/../g)?.map((x) => parseInt(x, 16)) ?? []);
  };

  const apiJSON = async (p, o) => {
    const r = await fetch(API + p, o);
    const j = await r.json();
    if (!j.ok) throw new Error(j.error || p);
    return j.data;
  };

  cvm.FC ??= new Map();
  cvm.HC ??= new Map();
  cvm.OV ??= new Map();
  cvm.ST ??= [];

  cvm.hex = hex;
  cvm.unhex = unhex;
  cvm.bytes = bytes;

  cvm.sha256 ??= async (x) =>
    new Uint8Array(await crypto.subtle.digest("SHA-256", bytes(x)));

  cvm.download_file ??= async (h) => {
    const r = await fetch(`${API}/api/file/${hex(h)}`);
    if (!r.ok) throw new Error("file not found");
    return new Uint8Array(await r.arrayBuffer());
  };

  cvm.getfirstchild ??= async (parent) => {
    const xs = (await apiJSON(`/api/children/${hex(parent)}`)).children;
    if (!xs.length) throw new Error("no child");
    return unhex(xs[0].hash);
  };

  const upload = async (file) =>
    unhex((await apiJSON("/api/upload", {
      method: "POST",
      body: bytes(file),
    })).hash);

  const download = async (h) => {
    const k = hex(h);
    if (!cvm.FC.has(k)) cvm.FC.set(k, await cvm.download_file(unhex(k)));
    return cvm.FC.get(k);
  };

  const userGet = async (keyHash) =>
    unhex((await apiJSON(`/api/user/get/${hex(cvm.USER)}/${hex(keyHash)}`)).value);

  const userSet = async (keyHash, fileHash) =>
    apiJSON(`/api/user/set/${hex(cvm.USER)}/${hex(keyHash)}/${hex(fileHash)}`, {
      method: "POST",
    });

  const u32 = (b, o) =>
    new DataView(b.buffer, b.byteOffset, b.byteLength).getUint32(o, true);

  const w32 = (b, o, n) =>
    new DataView(b.buffer, b.byteOffset, b.byteLength).setUint32(o, n, true);

  const zhash = (b, o = 0) => {
    b = bytes(b);
    if (o + 32 > b.length) return true;
    for (let i = o; i < o + 32; i++) if (b[i]) return false;
    return true;
  };

  const dlen = (o = cvm.PTR.off) =>
    zhash(cvm.PTR.buf, o) ? 0 : u32(cvm.PTR.buf, o + 32);

  const readHash = (o = cvm.PTR.off) =>
    cvm.PTR.buf.subarray(o, o + 32);

  const item = (x) => typeof x === "string"
    ? { hash: hex(x), data: new Uint8Array() }
    : { hash: hex(x.hash), data: bytes(x.data) };

  cvm.upload_file = upload;
  cvm.download = download;
  cvm.zhash = zhash;

  cvm.gethashhashfile = async (keyHash) => {
    const k = hex(keyHash);

    if (cvm.OV.has(k)) return cvm.OV.get(k);

    if (!cvm.HC.has(k)) {
      let h;
      if (cvm.USER) {
        try {
          h = await userGet(k);
        } catch {
          h = await cvm.getfirstchild(unhex(k));
        }
      } else {
        h = await cvm.getfirstchild(unhex(k));
      }
      cvm.HC.set(k, h);
    }

    return download(cvm.HC.get(k));
  };

  cvm.Modify_override = async () => {
    if (!cvm.USER) return;

    for (const [k, file] of cvm.OV) {
      const h = await upload(file);
      await userSet(k, h);
      cvm.HC.set(k, h);
      cvm.FC.set(hex(h), file);
    }

    cvm.OV.clear();
  };

  cvm.override = (keyHash, file) =>
    cvm.OV.set(hex(keyHash), bytes(file));

  cvm.user = (userId) => {
    cvm.USER = userId ? hex(userId) : "";
    cvm.HC.clear();
  };

  cvm.data = () =>
    cvm.PTR.buf.subarray(cvm.PTR.off + 36, cvm.PTR.off + 36 + dlen());

  cvm.buildBlock = (xs) => {
    xs = xs.map(item);

    const b = new Uint8Array(
      xs.reduce((n, x) => n + 36 + x.data.length, 32)
    );

    let o = 0;
    for (const x of xs) {
      const h = unhex(x.hash);
      if (h.length !== 32) throw new Error("bad item hash");

      b.set(h, o);
      o += 32;

      w32(b, o, x.data.length);
      o += 4;

      b.set(x.data, o);
      o += x.data.length;
    }

    return b;
  };

  cvm.parseBlock = (b) => {
    b = bytes(b);

    const xs = [];
    for (let o = 0; !zhash(b, o);) {
      if (o + 36 > b.length) throw new Error("bad block");

      const n = u32(b, o + 32);
      if (o + 36 + n > b.length) throw new Error("bad block");

      xs.push({
        hash: hex(b.subarray(o, o + 32)),
        data: b.slice(o + 36, o + 36 + n),
      });

      o += 36 + n;
    }

    return xs;
  };

  cvm.setprog = async (prog) => {
    cvm.PROG = prog.map(item);

    const file = cvm.buildBlock(cvm.PROG);
    cvm.PTR = { buf: file, off: 0 };

    cvm.override(ZERO, file);
  };

  cvm.execute_call ??= async (src) =>
    Function("CVM", "apiBase", `return (async()=>{${src}\n})()`)(cvm, API);

  cvm.executeBlock = async () => {
    for (;;) {
      await cvm.Modify_override();

      if (zhash(cvm.PTR.buf, cvm.PTR.off)) {
        const p = cvm.ST.pop();
        if (!p) return;

        cvm.PTR = p;
        return cvm.resume();
      }s

      const file = await cvm.gethashhashfile(readHash());

      if (file[0]) return cvm.execute_call(dec.decode(file));

      cvm.ST.push({
        buf: cvm.PTR.buf,
        off: cvm.PTR.off,
      });

      cvm.PTR = {
        buf: file,
        off: 0,
      };
    }
  };

  cvm.resume = async () => {
    cvm.PTR.off += 36 + dlen();
    return cvm.executeBlock();
  };

  cvm.runBlock = async (block = cvm.PTR.buf) => {
    cvm.PTR = { buf: bytes(block), off: 0 };
    cvm.ST = [];
    return cvm.executeBlock();
  };
})();

首启动程序,有一个网络文件浏览器,全零为根,显示文件文本内容而不是哈希值，而且需要 尝试显示 文本内容+ .svg 和 .describe

还有一个图形可视化节点编辑器,显示全零的节点集，双击节点可以打开节点集

末尾需要有个32字节全零代表结束，这个仅仅是标记，用于让编辑器查看时知道块结束了
例如
a
b
c
d
0000...
程序在d的时候就已经返回了，0000只是标记

而且要尽量分解,减少专用性

代码要短小精悍，尽量用轮子

生成上传脚本,这个ID已经通过验证了你直接拿来用
b4d13bff28b2ca67577761d2ccdd074ee1653bc45bbd9d27d8b886ab521cc134