#!/usr/bin/env python3
import argparse, hashlib, json, re, urllib.request
from pathlib import Path

BASE_DEFAULT = "http://124.221.146.23:8080"

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

  const cvm = CVM;
  const decoder = new TextDecoder();
  const zeroHash = "00".repeat(32);
  const emptyData = new Uint8Array();

  const unhex = (hex) =>
    new Uint8Array(hex.match(/../g).map((part) => parseInt(part, 16)));

  const asItem = (value) =>
    typeof value === "string" ? { hash: value, data: emptyData } : value;

  const children = async (hash) =>
    (await (await fetch(`${apiBase}/api/children/${hash}`)).json()).data.children;

  const label = async (hash) => {
    const bytes = await cvm.download_file(unhex(hash));
    const text = decoder.decode(bytes);
    return (text || hash).slice(0, 80);
  };

  if (!cvm.PROG) {
    cvm.PROG = cvm.parseBlock(cvm.PTR.buf);
  }

  document.head.insertAdjacentHTML("beforeend", `<style>
    .cvm-panel {
      position: fixed;
      z-index: 99999;
      width: 320px;
      max-height: 72vh;
      overflow: auto;
      padding: 8px;
      color: #ddd;
      background: #222;
      border: 1px solid #555;
      font: 12px/1.5 monospace;
    }
    .cvm-head {
      display: flex;
      justify-content: space-between;
      gap: 8px;
      margin-bottom: 8px;
      cursor: move;
      user-select: none;
    }
    .cvm-row,
    .cvm-drop {
      margin: 4px 0;
      padding: 4px 6px;
      background: #333;
      overflow: hidden;
      white-space: nowrap;
      text-overflow: ellipsis;
    }
    .cvm-row {
      cursor: pointer;
    }
    .cvm-drop {
      height: 8px;
      padding: 0;
      background: #555;
    }
    .cvm-drop:hover {
      background: #89b4fa;
    }
    .cvm-path {
      margin-bottom: 6px;
      color: #aaa;
      word-break: break-all;
    }
    .cvm-remove {
      float: right;
      color: #f38ba8;
    }
    #cvm-out {
      position: fixed;
      left: 50%;
      top: 14px;
      z-index: 99998;
      transform: translateX(-50%);
      padding: 6px 18px;
      color: #111;
      background: #a6e3a1;
      font: bold 28px system-ui;
    }
  </style>`);

  const dragPanel = (panel, handle) => {
    let startX = 0;
    let startY = 0;
    let panelX = 0;
    let panelY = 0;
    let dragging = false;

    handle.onmousedown = (event) => {
      if (event.target.closest("button")) return;

      dragging = true;
      startX = event.clientX;
      startY = event.clientY;

      const rect = panel.getBoundingClientRect();
      panelX = rect.left;
      panelY = rect.top;

      panel.style.left = `${panelX}px`;
      panel.style.top = `${panelY}px`;
      panel.style.right = "auto";

      event.preventDefault();
    };

    addEventListener("mousemove", (event) => {
      if (!dragging) return;

      panel.style.left = `${panelX + event.clientX - startX}px`;
      panel.style.top = `${panelY + event.clientY - startY}px`;
    });

    addEventListener("mouseup", () => {
      dragging = false;
    });
  };

  const makePanel = (title, action, style) => {
    const panel = document.createElement("div");

    panel.className = "cvm-panel";
    panel.style.cssText = style;
    panel.innerHTML = `
      <div class="cvm-head">
        <b>${title}</b>
        <button>${action}</button>
      </div>
      <div class="cvm-path"></div>
      <div class="cvm-list"></div>
    `;

    document.body.appendChild(panel);
    dragPanel(panel, panel.querySelector(".cvm-head"));

    return {
      button: panel.querySelector("button"),
      path: panel.querySelector(".cvm-path"),
      list: panel.querySelector(".cvm-list"),
    };
  };

  const browser = makePanel("文件浏览器", "上级", "left:16px;top:16px");
  const editor = makePanel("自编辑器 HTMLJSstart", "登录", "right:16px;top:16px");

  cvm.out = (text) => {
    let output = document.getElementById("cvm-out");

    if (!output) {
      output = document.createElement("div");
      output.id = "cvm-out";
      document.body.appendChild(output);
    }

    output.textContent = text;
  };

  cvm.browserStack = [zeroHash];

  const saveProgram = async () => {
    await cvm.setprog(cvm.PROG);
    await renderEditor();
  };

  const makeDrop = (index) => {
    const drop = document.createElement("div");

    drop.className = "cvm-drop";
    drop.ondragover = (event) => event.preventDefault();

    drop.ondrop = async (event) => {
      event.preventDefault();

      const hash = event.dataTransfer.getData("text/plain");
      cvm.PROG.splice(index, 0, { hash, data: emptyData });

      await saveProgram();
    };

    return drop;
  };

  async function renderBrowser() {
    const currentHash = cvm.browserStack.at(-1);

    browser.path.textContent = cvm.browserStack
      .map((hash) => hash.slice(0, 8))
      .join("/");

    browser.list.innerHTML = "";

    for (const child of await children(currentHash)) {
      const row = document.createElement("div");

      row.className = "cvm-row";
      row.draggable = true;
      row.textContent = `${await label(child.hash)} [${child.score}]`;

      row.ondragstart = (event) =>
        event.dataTransfer.setData("text/plain", child.hash);

      row.onclick = () => {
        cvm.browserStack.push(child.hash);
        renderBrowser();
      };

      browser.list.appendChild(row);
    }
  }

  async function renderEditor() {
    editor.path.textContent = "当前程序";
    editor.list.innerHTML = "";
    editor.list.appendChild(makeDrop(0));

    for (let index = 0; index < cvm.PROG.length; index++) {
      const programItem = asItem(cvm.PROG[index]);
      const row = document.createElement("div");
      const remove = document.createElement("span");

      row.className = "cvm-row";
      row.textContent = `${index}. ${await label(programItem.hash)}`;

      remove.className = "cvm-remove";
      remove.textContent = "x";
      remove.onclick = async () => {
        cvm.PROG.splice(index, 1);
        await saveProgram();
      };

      row.appendChild(remove);
      editor.list.appendChild(row);
      editor.list.appendChild(makeDrop(index + 1));
    }
  }

  browser.button.onclick = () => {
    if (cvm.browserStack.length > 1) {
      cvm.browserStack.pop();
      renderBrowser();
    }
  };

  editor.button.onclick = () => {
    cvm.user(prompt("user id").trim().toLowerCase());
  };

  cvm.renderBrowser = renderBrowser;
  cvm.renderEditor = renderEditor;

  await renderBrowser();
  await renderEditor();
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