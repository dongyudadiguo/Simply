#!/usr/bin/env python3
# upload_cvm.py
import argparse
import hashlib
import json
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

BASE_DEFAULT = "http://124.221.146.23:9000"

START_JS = r'''
(async () => {
  const cvm = CVM;
  const enc = new TextEncoder();
  const dec = new TextDecoder();

  const ZERO = "00".repeat(32);
  const HEX64 = /^[0-9a-f]{64}$/;

  const h = (x) =>
    typeof x === "string"
      ? x.toLowerCase()
      : [...x].map((b) => b.toString(16).padStart(2, "0")).join("");

  const unhex = (s) =>
    new Uint8Array((s.match(/../g) || []).map((x) => parseInt(x, 16)));

  const shaHex = async (s) =>
    h(new Uint8Array(await crypto.subtle.digest("SHA-256", enc.encode(s))));

  const esc = (s) =>
    String(s).replace(/[&<>"']/g, (c) => ({
      "&": "&amp;",
      "<": "&lt;",
      ">": "&gt;",
      '"': "&quot;",
      "'": "&#39;",
    }[c]));

  const oneLine = (bytes) =>
    dec.decode(bytes).replace(/\s+/g, " ").trim();

  const api = async (path, opt) => {
    const r = await fetch(`${apiBase}${path}`, opt);
    const j = await r.json();
    if (!j.ok) throw new Error(j.error || path);
    return j.data;
  };

  const download = async (hash) =>
    new Uint8Array(await fetch(`${apiBase}/api/file/${hash}`).then((r) => r.arrayBuffer()));

  const upload = async (bytes) =>
    (await api("/api/upload", { method: "POST", body: bytes })).hash;

  const children = async (parent) =>
    (await api(`/api/children/${parent}`)).children || [];

  const firstChild = async (parent) => {
    const xs = await children(parent);
    if (!xs.length) throw new Error("no child: " + parent);
    return xs[0].hash;
  };

  const userGet = async (key) =>
    (await api(`/api/user/get/${cvm.USER}/${key}`)).value;

  const userSet = async (key, file) =>
    api(`/api/user/set/${cvm.USER}/${key}/${file}`, { method: "POST" });

  const addEdge = async (parent, child) =>
    api(`/api/edge/${parent}/${child}`, { method: "POST" });

  const vote = async (parent, child) => {
    if (!cvm.USER) throw new Error("需要 user id 才能 vote");
    await api(`/api/vote/${cvm.USER}/${parent}/${child}`, { method: "POST" });
  };

  const resolveKey = async (key) => {
    if (cvm.USER) {
      try {
        return await userGet(key);
      } catch {}
    }
    return firstChild(key);
  };

  const saveOverride = async (key, bytes) => {
    const file = await upload(bytes);

    if (cvm.USER) {
      await userSet(key, file);
    }

    cvm.FC ??= new Map();
    cvm.HC ??= new Map();
    cvm.FC.set(file, bytes);
    cvm.HC.set(key, unhex(file));

    return file;
  };

  const publish = async (key, bytes) => {
    const file = await upload(bytes);
    await addEdge(key, file);
    await vote(key, file);
    return file;
  };

  const readU32 = (buf, off) =>
    new DataView(buf.buffer, buf.byteOffset + off, 4).getUint32(0, true);

  const sizeAt = (buf, off) => {
    if (off + 32 > buf.length) return 0;
    for (let i = off + 4; i < off + 32; i++) {
      if (buf[i] !== 0) return 0;
    }
    return readU32(buf, off);
  };

  const isZeroHashAt = (buf, off) => {
    if (off + 32 > buf.length) return false;
    for (let i = off; i < off + 32; i++) {
      if (buf[i] !== 0) return false;
    }
    return true;
  };

  const parseBlock = (buf) => {
    const rows = [];

    for (let off = 0; off + 32 <= buf.length;) {
      if (isZeroHashAt(buf, off)) {
        rows.push({ type: "end", off });
        break;
      }

      const n = sizeAt(buf, off);
      if (n) {
        rows.push({
          type: "bin",
          off,
          size: n,
          data: buf.subarray(off + 32, off + 32 + n),
        });
        off += 32 + n;
        continue;
      }

      rows.push({
        type: "hash",
        off,
        key: h(buf.subarray(off, off + 32)),
      });
      off += 32;
    }

    return rows;
  };

  const replaceRange = (buf, start, end, part) => {
    const out = new Uint8Array(buf.length - (end - start) + part.length);
    out.set(buf.subarray(0, start), 0);
    out.set(part, start);
    out.set(buf.subarray(end), start + part.length);
    return out;
  };

  const sizeChunk = (bytes) => {
    const out = new Uint8Array(32 + bytes.length);
    new DataView(out.buffer).setUint32(0, bytes.length, true);
    out.set(bytes, 32);
    return out;
  };

  let monacoPromise = null;

  const loadMonaco = () => {
    if (globalThis.monaco) return Promise.resolve(globalThis.monaco);
    if (monacoPromise) return monacoPromise;

    monacoPromise = new Promise((resolve, reject) => {
      const s = document.createElement("script");
      s.src = "https://cdn.jsdelivr.net/npm/monaco-editor@0.45.0/min/vs/loader.js";
      s.onload = () => {
        require.config({
          paths: {
            vs: "https://cdn.jsdelivr.net/npm/monaco-editor@0.45.0/min/vs",
          },
        });
        require(["vs/editor/editor.main"], () => resolve(monaco));
      };
      s.onerror = reject;
      document.head.appendChild(s);
    });

    return monacoPromise;
  };

  document.body.innerHTML = `
    <main class="app">
      <header>
        <button id="tabNet">网络</button>
        <button id="tabSelf">自身</button>
        <input id="user" placeholder="user id" spellcheck="false">
        <button id="setUser">用户</button>
        <span id="status"></span>
      </header>

      <section id="net" class="pane">
        <div class="bar">
          <button id="netUp">↑</button>
          <input id="netPath" spellcheck="false">
          <button id="netGo">打开</button>
        </div>
        <div id="netList" class="list"></div>
        <div class="bar">
          <input id="netText" placeholder="一行文本">
          <button id="netAdd">上传</button>
        </div>
      </section>

      <section id="self" class="pane hidden">
        <div class="bar">
          <button id="selfUp">↑</button>
          <button id="openStart">HTMLJSstart</button>
          <button id="saveSelf">覆盖</button>
          <button id="pubSelf">发布</button>
          <span id="selfTitle"></span>
        </div>
        <div id="blockList" class="list"></div>
        <div id="editor"></div>
      </section>
    </main>
  `;

  const style = document.createElement("style");
  style.textContent = `
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
      color: #161616;
      background: #f7f7f4;
    }
    .app {
      height: 100vh;
      display: grid;
      grid-template-rows: auto 1fr;
    }
    header, .bar {
      display: flex;
      gap: 8px;
      align-items: center;
      padding: 8px;
      border-bottom: 1px solid #d7d7d0;
      background: #fff;
    }
    button {
      height: 32px;
      padding: 0 10px;
      border: 1px solid #aaa;
      border-radius: 4px;
      background: #ecece2;
      font: inherit;
      cursor: pointer;
    }
    button:hover { background: #dfdfd1; }
    input {
      min-width: 0;
      flex: 1;
      height: 32px;
      padding: 0 8px;
      border: 1px solid #bbb;
      border-radius: 4px;
      font: inherit;
      background: #fff;
    }
    #status, #selfTitle {
      overflow: hidden;
      white-space: nowrap;
      text-overflow: ellipsis;
      color: #555;
    }
    .pane {
      min-height: 0;
      display: grid;
      grid-template-rows: auto 1fr auto;
    }
    #self {
      grid-template-rows: auto 220px 1fr;
    }
    .hidden { display: none; }
    .list {
      min-height: 0;
      overflow: auto;
      padding: 8px;
    }
    .row {
      display: grid;
      grid-template-columns: 80px 1fr 80px;
      gap: 10px;
      align-items: center;
      padding: 7px 8px;
      border-bottom: 1px solid #e0e0da;
      cursor: pointer;
    }
    .row:hover { background: #fff; }
    .kind, .score {
      color: #666;
      overflow: hidden;
      white-space: nowrap;
      text-overflow: ellipsis;
    }
    .txt {
      overflow: hidden;
      white-space: nowrap;
      text-overflow: ellipsis;
    }
    #editor {
      min-height: 0;
      border-top: 1px solid #d7d7d0;
    }
    textarea {
      width: 100%;
      height: 100%;
      min-height: 220px;
      resize: none;
      border: 0;
      padding: 10px;
      font: inherit;
      outline: none;
    }
  `;
  document.head.appendChild(style);

  const $ = (id) => document.getElementById(id);
  const status = (s) => $("status").textContent = s;

  cvm.USER = localStorage.getItem("cvm.user") || "";
  $("user").value = cvm.USER;

  $("setUser").onclick = () => {
    cvm.USER = $("user").value.trim().toLowerCase();
    localStorage.setItem("cvm.user", cvm.USER);
    status("user set");
  };

  $("tabNet").onclick = () => {
    $("net").classList.remove("hidden");
    $("self").classList.add("hidden");
  };

  $("tabSelf").onclick = () => {
    $("self").classList.remove("hidden");
    $("net").classList.add("hidden");
  };

  let netCur = ZERO;
  const netStack = [];

  const renderNet = async (parent, push = true) => {
    if (push && parent !== netCur) netStack.push(netCur);
    netCur = parent;
    $("netPath").value = parent;
    $("netList").innerHTML = `<div class="row"><div>...</div><div>loading</div><div></div></div>`;

    try {
      const xs = await children(parent);

      if (!xs.length) {
        $("netList").innerHTML = `<div class="row"><div>empty</div><div></div><div></div></div>`;
        return;
      }

      const rows = await Promise.all(xs.map(async (x) => {
        let text = "";
        try {
          text = oneLine(await download(x.hash));
        } catch {
          text = "";
        }

        return `
          <div class="row" data-net="${x.hash}">
            <div class="kind">${x.hash.slice(0, 12)}</div>
            <div class="txt">${esc(text)}</div>
            <div class="score">${x.score}</div>
          </div>
        `;
      }));

      $("netList").innerHTML = rows.join("");
    } catch (e) {
      $("netList").innerHTML = `<div class="row"><div>err</div><div>${esc(e.message)}</div><div></div></div>`;
    }
  };

  $("netList").onclick = (e) => {
    const row = e.target.closest("[data-net]");
    if (row) renderNet(row.dataset.net);
  };

  $("netGo").onclick = () => {
    const x = $("netPath").value.trim().toLowerCase();
    if (HEX64.test(x)) renderNet(x);
  };

  $("netUp").onclick = () => {
    if (netStack.length) renderNet(netStack.pop(), false);
  };

  $("netAdd").onclick = async () => {
    const text = $("netText").value;
    if (!text) return;

    status("uploading");
    const file = await upload(enc.encode(text));
    await addEdge(netCur, file);
    $("netText").value = "";
    await renderNet(netCur, false);
    status("uploaded");
  };

  let startKey = await shaHex("HTMLJSstart");
  let ctx = null;
  const selfStack = [];
  let editorDispose = null;
  let activeSave = null;

  const setEditorHtml = (html) => {
    if (editorDispose) {
      editorDispose();
      editorDispose = null;
    }
    $("editor").innerHTML = html;
  };

  const renderBlock = () => {
    $("selfTitle").textContent = ctx.key;
    $("blockList").innerHTML = parseBlock(ctx.bytes).map((r) => {
      if (r.type === "end") {
        return `<div class="row"><div class="kind">end</div><div class="txt">${ZERO}</div><div></div></div>`;
      }

      if (r.type === "bin") {
        return `
          <div class="row" data-bin="${r.off}">
            <div class="kind">bin</div>
            <div class="txt">${r.size} bytes</div>
            <div></div>
          </div>
        `;
      }

      return `
        <div class="row" data-key="${r.key}">
          <div class="kind">hash</div>
          <div class="txt">${r.key}</div>
          <div></div>
        </div>
      `;
    }).join("");
  };

  const openBlockByKey = async (key, push = true) => {
    status("opening block");
    const file = await resolveKey(key);
    const bytes = await download(file);

    if (push && ctx) selfStack.push(ctx);
    ctx = { key, file, bytes };
    renderBlock();
    setEditorHtml(`<textarea readonly>${esc(oneLine(bytes))}</textarea>`);
    status("block opened");
  };

  const openJs = async (key, bytes) => {
    status("opening js");
    const source = dec.decode(bytes);

    try {
      const m = await loadMonaco();
      setEditorHtml("");
      const ed = m.editor.create($("editor"), {
        value: source,
        language: "javascript",
        automaticLayout: true,
        minimap: { enabled: false },
        fontSize: 13,
      });

      let timer = 0;
      ed.onDidChangeModelContent(() => {
        clearTimeout(timer);
        timer = setTimeout(async () => {
          try {
            status("saving override");
            await saveOverride(key, enc.encode(ed.getValue()));
            status("override saved");
          } catch (e) {
            status(e.message);
          }
        }, 700);
      });

      activeSave = async (mode) => {
        const bytes = enc.encode(ed.getValue());
        if (mode === "publish") return publish(key, bytes);
        return saveOverride(key, bytes);
      };

      editorDispose = () => ed.dispose();
    } catch {
      setEditorHtml(`<textarea id="fallbackJs">${esc(source)}</textarea>`);
      const ta = $("fallbackJs");

      ta.oninput = () => {
        clearTimeout(ta._timer);
        ta._timer = setTimeout(async () => {
          try {
            await saveOverride(key, enc.encode(ta.value));
            status("override saved");
          } catch (e) {
            status(e.message);
          }
        }, 700);
      };

      activeSave = async (mode) => {
        const bytes = enc.encode(ta.value);
        if (mode === "publish") return publish(key, bytes);
        return saveOverride(key, bytes);
      };
    }

    status("js editor ready");
  };

  const openBin = (off) => {
    const n = sizeAt(ctx.bytes, off);
    const oldEnd = off + 32 + n;
    const oldData = ctx.bytes.subarray(off + 32, oldEnd);

    setEditorHtml(`<textarea id="binEdit" spellcheck="false">${h(oldData)}</textarea>`);

    activeSave = async (mode) => {
      const raw = $("binEdit").value.replace(/\s+/g, "").toLowerCase();
      if (raw.length % 2 || /[^0-9a-f]/.test(raw)) {
        throw new Error("bad hex");
      }

      const nextData = unhex(raw);
      ctx.bytes = replaceRange(ctx.bytes, off, oldEnd, sizeChunk(nextData));
      renderBlock();

      if (mode === "publish") return publish(ctx.key, ctx.bytes);
      return saveOverride(ctx.key, ctx.bytes);
    };
  };

  $("blockList").onclick = async (e) => {
    const bin = e.target.closest("[data-bin]");
    if (bin) {
      openBin(Number(bin.dataset.bin));
      return;
    }

    const row = e.target.closest("[data-key]");
    if (!row) return;

    const key = row.dataset.key;
    status("resolving");
    const file = await resolveKey(key);
    const bytes = await download(file);

    if (bytes[0]) {
      await openJs(key, bytes);
    } else {
      await openBlockByKey(key);
    }
  };

  $("openStart").onclick = () => openBlockByKey(startKey, false);

  $("selfUp").onclick = () => {
    if (!selfStack.length) return;
    ctx = selfStack.pop();
    renderBlock();
    setEditorHtml(`<textarea readonly>${esc(oneLine(ctx.bytes))}</textarea>`);
  };

  $("saveSelf").onclick = async () => {
    if (!activeSave && ctx) activeSave = () => saveOverride(ctx.key, ctx.bytes);
    if (!activeSave) return;

    try {
      status("saving override");
      await activeSave("override");
      status("override saved");
    } catch (e) {
      status(e.message);
    }
  };

  $("pubSelf").onclick = async () => {
    if (!activeSave && ctx) activeSave = () => publish(ctx.key, ctx.bytes);
    if (!activeSave) return;

    try {
      status("publishing");
      await activeSave("publish");
      status("published");
    } catch (e) {
      status(e.message);
    }
  };

  renderNet(ZERO, false);
  await openBlockByKey(startKey, false);
})();
'''


CONTINUE_JS = "CVM.PTR.off = 0;\nreturn CVM.executeBlock();\n"

ZERO_HASH = b"\x00" * 32


def sha(b: bytes) -> bytes:
    return hashlib.sha256(b).digest()


def key(name: str) -> bytes:
    return sha(name.encode())


def block(names) -> bytes:
    # 新格式：连续 32 字节 hash；末尾全零 hash 只是查看/编辑时的终止标记。
    return b"".join(key(name) for name in names) + ZERO_HASH


def read_id(path: str) -> str:
    raw = Path(path).read_bytes()

    if len(raw) == 32:
        return raw.hex()

    t = raw.strip()

    if re.fullmatch(rb"[0-9a-fA-F]{64}", t):
        return t.decode().lower()

    m = re.search(rb"[0-9a-fA-F]{64}", raw)
    if m:
        return m.group(0).decode().lower()

    raise SystemExit("id.bin 必须是 32 字节 raw id，或 64 位 hex")


class API:
    def __init__(self, base: str):
        self.base = base.rstrip("/")

    def call(self, method: str, path: str, data=b""):
        req = urllib.request.Request(self.base + path, data=data, method=method)

        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                body = r.read()
        except urllib.error.HTTPError as e:
            body = e.read()
            raise RuntimeError(
                f"{method} {path} HTTP {e.code}: {body.decode(errors='replace')}"
            )

        obj = json.loads(body.decode())

        if not obj.get("ok"):
            raise RuntimeError(f"{method} {path}: {obj}")

        return obj

    def upload(self, data: bytes):
        obj = self.call("POST", "/api/upload", data)
        return obj["data"]["hash"], obj

    def edge(self, parent: str, child: str):
        return self.call("POST", f"/api/edge/{parent}/{child}")

    def vote(self, user: str, parent: str, child: str):
        return self.call("POST", f"/api/vote/{user}/{parent}/{child}")


def upload_edge_vote(api: API, user: str, parent_name: str, file_name: str, data: bytes):
    parent = key(parent_name).hex()
    local_hash = sha(data).hex()

    uploaded, upload_result = api.upload(data)

    if uploaded != local_hash:
        raise RuntimeError(f"hash mismatch: {file_name}")

    edge_result = api.edge(parent, uploaded)
    vote_result = api.vote(user, parent, uploaded)

    print(f"{parent_name} -> {file_name}")
    print("  parent key :", parent)
    print("  file hash  :", uploaded)
    print("  upload     :", upload_result)
    print("  edge       :", edge_result)
    print("  vote       :", vote_result)
    print()

    return uploaded


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default=BASE_DEFAULT)
    ap.add_argument("--id", default="id.bin")
    args = ap.parse_args()

    api = API(args.base)
    user = read_id(args.id)

    print("base:", args.base)
    print("user:", user)
    print()

    # 新启动块格式：
    #
    # HTMLJSstart -> start.bin
    #
    # start.bin:
    #   [start]
    #   [continue]
    #   [0000000000000000000000000000000000000000000000000000000000000000]
    #
    # 全零 hash 只是块查看/编辑时的终止标记，不再上传 blockend。
    upload_edge_vote(api, user, "start", "start.js", START_JS.encode())
    upload_edge_vote(api, user, "continue", "continue.js", CONTINUE_JS.encode())
    upload_edge_vote(api, user, "HTMLJSstart", "start.bin", block(["start", "continue"]))

    print("完成。")
    print("start.bin 格式：")
    print("  [start]")
    print("  [continue]")
    print("  [zero hash marker]")
    print()
    print("没有上传 blockend，没有上传 HTMLJSroot，没有上传 root.bin。")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print("ERROR:", e, file=sys.stderr)
        sys.exit(1)