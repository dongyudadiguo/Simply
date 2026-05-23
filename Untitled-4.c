以下是服务器代码

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

以下是虚拟机代码

<script>
const host = "124.221.146.23";
const port = 9000;
const apiBase = location.origin == "null" ? `http://${host}:${port}` : location.origin;

const textEncoder = new TextEncoder();
const textDecoder = new TextDecoder();

const CVM = globalThis.CVM = {
  BASE: null,
  PTR: null,
  IMP: null,
};

const toBytes = (value) =>
  value instanceof Uint8Array ? value :
  value instanceof ArrayBuffer ? new Uint8Array(value) :
  ArrayBuffer.isView(value) ? new Uint8Array(value.buffer, value.byteOffset, value.byteLength) :
  textEncoder.encode(String(value));

const toHex = (value) =>
  [...toBytes(value)].map((byte) => byte.toString(16).padStart(2, "0")).join("");

const sha256 = async (value) =>
  new Uint8Array(await crypto.subtle.digest("SHA-256", toBytes(value)));

const downloadFile = async (hash) =>
  new Uint8Array(await (await fetch(`${apiBase}/api/file/${toHex(hash)}`)).arrayBuffer());

Object.assign(CVM, {
  sha256,
  str_sha: sha256,
  hex: toHex,
  download_file: downloadFile,
  execute_call: (source) => eval(`(async()=>{${source}})()`),
});

(async () => {
  const startFileData = await downloadFile(await sha256("HTMLJSstart"));

  CVM.BASE = CVM.PTR = {
    buf: startFileData,
    off: 0,
  };

  const javaScriptHash = startFileData.subarray(0, 32);
  const javaScriptSource = textDecoder.decode(await downloadFile(javaScriptHash));

  CVM.IMP = () => eval(`(async()=>{${javaScriptSource}})()`);
  await CVM.IMP();
})();
</script>


我想制作以下函数用于标准的指令持续

{
    ptr += sizeof(hash) // 跳过当前hash
    while ((n = *(uint256 *)ptr) < uint32的最大值) { 
        ptr += sizeof(hash) + n 
    } // 跳过数据

    while (true)
    {
        file = get(ptrhash) // 没有缓存就下载,先用usergethash没有再getfirstchild ptrhash-ptr指向的sha256
        if (Executable(file))
        {
            execute(file)
            break
        }
        else
        {
            check 没有就添加，有就对它检查。检查是否有改动。如果有改动，那就。setuserhash
            push // 记录返回点
            ptr = 文件加载到内存中的地址
        }
    }
}
