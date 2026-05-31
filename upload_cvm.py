#!/usr/bin/env python3
import argparse, hashlib, json, re, urllib.request
from pathlib import Path

BASE_DEFAULT = "http://124.221.146.23:9000"

START_JS = r"""
// ============================================================
// 标准持续函数
// ============================================================
(() => {
  const cvm = CVM, dec = new TextDecoder(), enc = new TextEncoder();
  const hex = (x) => typeof x === "string" ? x : cvm.hex(x);
  const unhex = (h) => new Uint8Array(h.match(/../g).map((x) => parseInt(x, 16)));
  const bytes = (x) => x instanceof Uint8Array ? x :
    x instanceof ArrayBuffer ? new Uint8Array(x) :
    ArrayBuffer.isView(x) ? new Uint8Array(x.buffer, x.byteOffset, x.byteLength) :
    enc.encode(String(x ?? ""));

  const u32 = (b, o) => new DataView(b.buffer, b.byteOffset, b.byteLength).getUint32(o, true);
  const w32 = (b, o, n) => new DataView(b.buffer, b.byteOffset, b.byteLength).setUint32(o, n, true);
  const zhash = (b, o) => {
    if (o + 32 > b.length) return true;
    for (let i = o; i < o + 32; i++) if (b[i]) return false;
    return true;
  };
  const readHash = (o = cvm.PTR.off) => cvm.PTR.buf.subarray(o, o + 32);
  const item = (x) => typeof x === "string" ? { hash: x, data: new Uint8Array() } :
    { hash: x.hash, data: bytes(x.data) };
  const dlen = (o = cvm.PTR.off) => zhash(cvm.PTR.buf, o) ? 0 : u32(cvm.PTR.buf, o + 32);

  cvm.FC ??= new Map();
  cvm.HC ??= new Map();
  cvm.OV ??= new Map();
  cvm.ST ??= [];

  const download = async (h) => {
    const k = hex(h);
    if (!cvm.FC.has(k)) cvm.FC.set(k, await cvm.download_file(h));
    return cvm.FC.get(k);
  };

  const upload = async (file) =>
    unhex((await (await fetch(`${apiBase}/api/upload`, { method: "POST", body: file })).json()).data.hash);

  const userGet = async (keyHash) =>
    unhex((await (await fetch(`${apiBase}/api/user/get/${hex(cvm.USER)}/${hex(keyHash)}`)).json()).data.value);

  const userSet = async (keyHash, fileHash) =>
    fetch(`${apiBase}/api/user/set/${hex(cvm.USER)}/${hex(keyHash)}/${hex(fileHash)}`, { method: "POST" });

  cvm.gethashhashfile = async (keyHash) => {
    const k = hex(keyHash);
    if (cvm.OV.has(k)) return cvm.OV.get(k);
    if (!cvm.HC.has(k)) {
      let h;
      if (cvm.USER) { try { h = await userGet(keyHash); } catch { h = await cvm.getfirstchild(keyHash); } }
      else h = await cvm.getfirstchild(keyHash);
      cvm.HC.set(k, h);
    }
    return download(cvm.HC.get(k));
  };

  cvm.Modify_override = async () => {
    if (!cvm.USER) return;
    for (const [k, file] of cvm.OV) {
      const h = await upload(file);
      await userSet(unhex(k), h);
      cvm.HC.set(k, h);
      cvm.FC.set(hex(h), file);
    }
    cvm.OV.clear();
  };

  cvm.override = (keyHash, file) => cvm.OV.set(hex(keyHash), file);
  cvm.user = (userId) => { cvm.USER = hex(userId); cvm.HC.clear(); };
  cvm.data = () => cvm.PTR.buf.subarray(cvm.PTR.off + 36, cvm.PTR.off + 36 + dlen());

  cvm.buildBlock = (xs) => {
    xs = xs.map(item);
    const b = new Uint8Array(xs.reduce((n, x) => n + 36 + x.data.length, 32));
    let o = 0;
    for (const x of xs) {
      b.set(unhex(x.hash), o); o += 32;
      w32(b, o, x.data.length); o += 4;
      b.set(x.data, o); o += x.data.length;
    }
    return b;
  };

  cvm.parseBlock = (b) => {
    const xs = [];
    for (let o = 0; !zhash(b, o);) {
      const n = u32(b, o + 32);
      xs.push({ hash: hex(b.subarray(o, o + 32)), data: b.slice(o + 36, o + 36 + n) });
      o += 36 + n;
    }
    return xs;
  };

  cvm.setprog = async (prog) => {
    cvm.PROG = prog.map(item);
    const file = cvm.buildBlock(cvm.PROG);
    cvm.PTR = { buf: file, off: 0 };
    cvm.override(await cvm.sha256("HTMLJSstart"), file);
  };

  cvm.executeBlock = async () => {
    for (;;) {
      await cvm.Modify_override();

      if (zhash(cvm.PTR.buf, cvm.PTR.off)) {
        const p = cvm.ST.pop();
        if (!p) return;
        cvm.PTR = p;
        return cvm.resume();
      }

      const file = await cvm.gethashhashfile(readHash());
      if (file[0]) return cvm.execute_call(dec.decode(file));

      cvm.ST.push({ buf: cvm.PTR.buf, off: cvm.PTR.off });
      cvm.PTR = { buf: file, off: 0 };
    }
  };

  cvm.resume = async () => {
    cvm.PTR.off += 36 + dlen();
    return cvm.executeBlock();
  };
})();


// ============================================================
// 其他代码：文件浏览器 + 自编辑器
// ============================================================
if (!CVM.__ui) {
  CVM.__ui = true;
  await (async () => {
    const cvm = CVM, dec = new TextDecoder();
    const hex = (x) => typeof x === "string" ? x : cvm.hex(x);
    const unhex = (h) => new Uint8Array(h.match(/../g).map((x) => parseInt(x, 16)));
    const ZERO = "00".repeat(32);
    const esc = (s) => s.replace(/[&<>]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c]));
    const item = (x) => typeof x === "string" ? { hash: x, data: new Uint8Array() } : x;

    if (!cvm.PROG) cvm.PROG = cvm.parseBlock(cvm.PTR.buf);

    const kids = async (h) =>
      ((await (await fetch(`${apiBase}/api/children/${h}`)).json()).data || {}).children || [];

    const labels = new Map();
    const label = async (h) => {
      if (labels.has(h)) return labels.get(h);
      let v;
      try {
        const b = await cvm.download_file(unhex(h)), t = dec.decode(b);
        v = b.length && /[^\x09\x0a\x0d\x20-\x7e]/.test(t) ? `[${b.length}B] ${h.slice(0, 12)}...` : (t || "(空)");
      } catch { v = h.slice(0, 12) + "..."; }
      labels.set(h, v);
      return v;
    };

    cvm.out = (s) => {
      let o = document.getElementById("cvm-out");
      if (!o) { o = document.createElement("div"); o.id = "cvm-out"; document.body.appendChild(o); }
      o.textContent = s;
    };

    document.head.insertAdjacentHTML("beforeend", `<style>
      .cvm-panel{position:fixed;z-index:99999;background:#1e1e2e;color:#cdd6f4;font:12px/1.5 monospace;border:1px solid #45475a;border-radius:8px;box-shadow:0 8px 24px #0008;width:320px;max-height:72vh;display:flex;flex-direction:column}
      .cvm-head{padding:6px 10px;background:#313244;cursor:move;border-radius:8px 8px 0 0;display:flex;justify-content:space-between;gap:8px;align-items:center;user-select:none}
      .cvm-head span+span{cursor:pointer;color:#89b4fa}.cvm-body{padding:8px;overflow:auto}.cvm-path{color:#9399b2;margin-bottom:6px;word-break:break-all}
      .cvm-row{padding:4px 6px;margin:2px 0;background:#313244;border-radius:4px;cursor:grab;display:flex;gap:6px;align-items:center;white-space:nowrap;overflow:hidden}
      .cvm-row:hover{background:#45475a}.cvm-row b{color:#89b4fa}.cvm-tag{color:#a6e3a1}.cvm-x{color:#f38ba8;cursor:pointer;margin-left:auto}
      .cvm-drop{height:10px;border:1px dashed #585b70;border-radius:4px;margin:2px 0}.cvm-drop.over{height:22px;border-color:#89b4fa;background:#313244}
      #cvm-out{position:fixed;left:50%;top:14px;transform:translateX(-50%);z-index:99998;font:bold 30px/1.4 system-ui;color:#1e1e2e;background:#a6e3a1;padding:6px 20px;border-radius:10px;box-shadow:0 4px 12px #0005}
    </style>`);

    const drag = (p, h) => {
      let sx, sy, x, y, on = false;
      h.onmousedown = (e) => {
        if (e.target !== h && e.target.tagName === "SPAN" && e.target !== h.firstElementChild) return;
        on = true; sx = e.clientX; sy = e.clientY;
        const r = p.getBoundingClientRect(); x = r.left; y = r.top; e.preventDefault();
      };
      addEventListener("mousemove", (e) => {
        if (!on) return;
        p.style.left = x + e.clientX - sx + "px"; p.style.top = y + e.clientY - sy + "px"; p.style.right = "auto";
      });
      addEventListener("mouseup", () => on = false);
    };

    const panel = (html, pos) => {
      const p = document.createElement("div");
      p.className = "cvm-panel"; Object.assign(p.style, pos); p.innerHTML = html; document.body.appendChild(p);
      drag(p, p.querySelector(".cvm-head"));
      return p;
    };

    const fb = panel(`<div class="cvm-head"><span>文件浏览器</span><span id="fb-up">上级</span></div><div class="cvm-body"><div class="cvm-path" id="fb-path"></div><div id="fb-list"></div></div>`, { left: "16px", top: "16px" });
    const ed = panel(`<div class="cvm-head"><span>自编辑器 HTMLJSstart</span><span id="ed-user">登录</span></div><div class="cvm-body"><div id="ed-list"></div></div>`, { right: "16px", top: "16px" });

    cvm.fbStack = [ZERO];

    const renderBrowser = async () => {
      const cur = cvm.fbStack.at(-1), box = fb.querySelector("#fb-list");
      fb.querySelector("#fb-path").textContent = "root/" + cvm.fbStack.slice(1).map((h) => h.slice(0, 8)).join("/");
      box.textContent = "加载中...";
      box.innerHTML = "";
      for (const c of await kids(cur)) {
        const r = document.createElement("div");
        r.className = "cvm-row"; r.draggable = true;
        r.innerHTML = `<b>></b><span>${esc(await label(c.hash))}</span><span class="cvm-tag">[${c.score}]</span>`;
        r.ondragstart = (e) => e.dataTransfer.setData("text/plain", c.hash);
        r.onclick = () => { cvm.fbStack.push(c.hash); renderBrowser(); };
        box.appendChild(r);
      }
      if (!box.children.length) box.textContent = "(无子节点)";
    };

    const changed = async () => { await cvm.setprog(cvm.PROG); renderEditor(); };

    const drop = (i) => {
      const z = document.createElement("div");
      z.className = "cvm-drop";
      z.ondragover = (e) => { e.preventDefault(); z.classList.add("over"); };
      z.ondragleave = () => z.classList.remove("over");
      z.ondrop = async (e) => {
        e.preventDefault(); z.classList.remove("over");
        const h = e.dataTransfer.getData("text/plain");
        if (h) { cvm.PROG.splice(i, 0, { hash: h, data: new Uint8Array() }); await changed(); }
      };
      return z;
    };

    async function renderEditor() {
      const box = ed.querySelector("#ed-list");
      box.innerHTML = ""; box.appendChild(drop(0));
      for (let i = 0; i < cvm.PROG.length; i++) {
        const it = item(cvm.PROG[i]), r = document.createElement("div");
        r.className = "cvm-row";
        r.innerHTML = `<b>${i}</b><span>${esc(await label(it.hash))}</span>${it.data.length ? `<span class="cvm-tag">[${it.data.length}B]</span>` : ""}<span class="cvm-x">x</span>`;
        r.querySelector(".cvm-x").onclick = async () => { cvm.PROG.splice(i, 1); await changed(); };
        box.appendChild(r); box.appendChild(drop(i + 1));
      }
    }

    fb.querySelector("#fb-up").onclick = () => { if (cvm.fbStack.length > 1) { cvm.fbStack.pop(); renderBrowser(); } };
    ed.querySelector("#ed-user").onclick = () => { const id = prompt("user id"); if (id) cvm.user(id.trim().toLowerCase()); };

    cvm.renderBrowser = renderBrowser;
    cvm.renderEditor = renderEditor;
    await renderBrowser();
    await renderEditor();
  })();
}


// ============================================================
// 其他代码：持续入口
// ============================================================
{
  const cvm = CVM;
  cvm.PTR.buf = cvm.buildBlock(cvm.PROG);
  cvm.PTR.off = 0;
  await new Promise((r) => setTimeout(r, 60));
  return cvm.resume();
}
"""

CONTINUE_JS = "CVM.PTR.off=0;return CVM.executeBlock();\n"
PRINT_JS = 'CVM.out("hello world");return CVM.resume();\n'

ZERO_HASH = b"\x00" * 32

def sha(b): return hashlib.sha256(b).digest()
def key(s): return sha(s.encode())
def block(names): return b"".join(key(s) + (0).to_bytes(4, "little") for s in names) + ZERO_HASH

def read_id(path):
    raw = Path(path).read_bytes()
    return raw.hex() if len(raw) == 32 else re.search(rb"[0-9a-fA-F]{64}", raw).group(0).decode().lower()

class API:
    def __init__(self, base): self.base = base.rstrip("/")
    def call(self, method, path, data=b""):
        return json.loads(urllib.request.urlopen(urllib.request.Request(self.base + path, data=data, method=method)).read().decode())
    def upload(self, data): return self.call("POST", "/api/upload", data)["data"]["hash"]
    def edge(self, p, c): self.call("POST", f"/api/edge/{p}/{c}")
    def vote(self, u, p, c): self.call("POST", f"/api/vote/{u}/{p}/{c}")

def put(api, user, parent_name, data):
    parent, child = key(parent_name).hex(), sha(data).hex()
    api.upload(parent_name.encode())
    api.upload(data)
    api.edge(parent, child)
    api.vote(user, parent, child)
    print(parent_name, "->", child)
    return child

def root(api, user, name):
    child = key(name).hex()
    api.edge(ZERO_HASH.hex(), child)
    api.vote(user, ZERO_HASH.hex(), child)
    print("root ->", name, child)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default=BASE_DEFAULT)
    ap.add_argument("--id", default="id.bin")
    args = ap.parse_args()

    api, user = API(args.base), read_id(args.id)
    print("base:", args.base)
    print("user:", user)

    put(api, user, "start", START_JS.encode())
    put(api, user, "continue", CONTINUE_JS.encode())
    put(api, user, "print", PRINT_JS.encode())
    put(api, user, "HTMLJSstart", block(["start", "continue"]))
    root(api, user, "print")
    print("完成")

main()