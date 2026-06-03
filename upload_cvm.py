#!/usr/bin/env python3
import argparse, hashlib, json, re, urllib.request, os
from pathlib import Path

BASE_DEFAULT = "http://124.221.146.23:9000"
ZERO_HASH = b"\x00" * 32

def sha(b): return hashlib.sha256(b).digest()
def key(s): return sha(s.encode())

def block(names):
    out = bytearray()
    for name in names:
        out += key(name)
        out += (0).to_bytes(4, "little")
    out += ZERO_HASH
    return bytes(out)

class API:
    def __init__(self, base):
        self.base = base.rstrip("/")
    def call(self, method, path, data=b"", headers=None):
        req = urllib.request.Request(self.base + path, data=data, method=method, headers=headers or {})
        return json.loads(urllib.request.urlopen(req).read().decode())
    def upload(self, data):
        return self.call("POST", "/api/upload", data)["data"]["hash"]
    def edge(self, p, c):
        self.call("POST", f"/api/edge/{p}/{c}")
    def vote(self, u, p, c):
        self.call("POST", f"/api/vote/{u}/{p}/{c}")

def get_or_create_id(api, path):
    p = Path(path)
    if p.exists():
        raw = p.read_bytes()
        if len(raw) == 32: return raw.hex()
        m = re.search(rb"[0-9a-fA-F]{64}", raw)
        if m: return m.group(0).decode().lower()
    
    print("id.bin 不存在，正在注册新用户...")
    req = urllib.request.Request(api.base + "/api/register", data=json.dumps({"token": ""}).encode(), method="POST", headers={"Content-Type": "application/json"})
    res = json.loads(urllib.request.urlopen(req).read().decode())
    if not res.get("ok"):
        raise RuntimeError("register failed: " + res.get("error", "unknown"))
    
    new_id = res["data"]["id"]
    p.write_bytes(bytes.fromhex(new_id))
    print(f"已注册并保存新用户: {new_id}")
    return new_id

def put(api, user, name, data):
    parent = key(name).hex()
    child = sha(data).hex()
    api.upload(name.encode())
    got = api.upload(data)
    if got != child:
        raise RuntimeError(f"hash mismatch: {name}")
    api.edge(parent, child)
    api.vote(user, parent, child)
    print(f"[+] {name} -> {child[:16]}...")
    return child

def root(api, user, name):
    parent = ZERO_HASH.hex()
    child = key(name).hex()
    api.edge(parent, child)
    api.vote(user, parent, child)

# ==========================================
# 1. 核心启动文件 (Stable Studio + VM Engine)
# ==========================================
START_JS = r"""

// ============================================================
// 标准持续函数 + std/stdoffset 标准参数缓存
// ============================================================
(() => {
  const cvm = CVM, dec = new TextDecoder(), enc = new TextEncoder();

  const hex = (x) => typeof x === "string" ? x : cvm.hex(x);

  const unhex = (h) =>
    new Uint8Array(h.match(/../g).map((x) => parseInt(x, 16)));

  const bytes = (x) => x instanceof Uint8Array ? x :
    x instanceof ArrayBuffer ? new Uint8Array(x) :
    ArrayBuffer.isView(x) ? new Uint8Array(x.buffer, x.byteOffset, x.byteLength) :
    enc.encode(String(x ?? ""));

  const u32 = (b, o) =>
    new DataView(b.buffer, b.byteOffset, b.byteLength).getUint32(o, true);

  const w32 = (b, o, n) =>
    new DataView(b.buffer, b.byteOffset, b.byteLength).setUint32(o, n >>> 0, true);

  const zhash = (b, o) => {
    if (o + 32 > b.length) return true;
    for (let i = o; i < o + 32; i++) if (b[i]) return false;
    return true;
  };

  const readHash = (o = cvm.PTR.off) => cvm.PTR.buf.subarray(o, o + 32);

  const item = (x) => typeof x === "string"
    ? { hash: x, data: new Uint8Array() }
    : {
        hash: typeof x.hash === "string" ? x.hash : hex(x.hash),
        data: bytes(x.data),
      };

  const dlen = (o = cvm.PTR.off) =>
    zhash(cvm.PTR.buf, o) ? 0 : u32(cvm.PTR.buf, o + 32);

  cvm.FC ??= new Map();
  cvm.HC ??= new Map();
  cvm.OV ??= new Map();
  cvm.ST ??= [];

  cvm.std ??= new Uint8Array(1024);
  cvm.stdsize ??= 0;
  cvm.stdoffset ??= 0;

  cvm.stdEnsure = (need) => {
    if (cvm.std.length >= need) return;
    let n = cvm.std.length || 1024;
    while (n < need) n *= 2;
    const b = new Uint8Array(n);
    b.set(cvm.std);
    cvm.std = b;
  };

  cvm.stdInput = () => {
    cvm.stdoffset = 0;
    return cvm.std;
  };

  cvm.stdRead = (n) => {
    n = Math.max(0, n | 0);
    const o = cvm.stdoffset | 0;
    const end = Math.min(cvm.stdsize || cvm.std.length, o + n);
    const out = cvm.std.slice(o, end);
    cvm.stdoffset = o + n;
    return out;
  };

  cvm.stdBool = () => {
    cvm.stdInput();
    return !!cvm.stdRead(1)[0];
  };

  cvm.stdWrite = (data) => {
    data = bytes(data);
    const o = cvm.stdoffset | 0;
    cvm.stdEnsure(o + data.length);
    cvm.std.set(data, o);
    cvm.stdoffset = o + data.length;
    cvm.stdsize = Math.max(cvm.stdsize || 0, cvm.stdoffset);
    return data.length;
  };

  cvm.stdReturn = (data) => {
    cvm.stdoffset = 0;
    cvm.stdsize = 0;
    cvm.stdWrite(data);
    return data;
  };

  cvm.VAR ??= new Map();
  cvm.VSZ ??= new Map();

  cvm.varKey = (id) => hex(id);

  cvm.setVarSize = (id, size) => {
    const k = cvm.varKey(id);
    size = Math.max(0, size >>> 0);
    cvm.VSZ.set(k, size);

    const old = cvm.VAR.get(k) || new Uint8Array();
    const next = new Uint8Array(size);
    next.set(old.subarray(0, size));
    cvm.VAR.set(k, next);

    return next;
  };

  cvm.getVar = (id) => {
    const k = cvm.varKey(id);
    if (!cvm.VAR.has(k)) {
      cvm.VAR.set(k, new Uint8Array(cvm.VSZ.get(k) || 0));
    }
    return cvm.VAR.get(k);
  };

  cvm.setVar = (id, data) => {
    const k = cvm.varKey(id);
    const size = cvm.VSZ.get(k) ?? bytes(data).length;
    const next = new Uint8Array(size);
    next.set(bytes(data).subarray(0, size));
    cvm.VSZ.set(k, size);
    cvm.VAR.set(k, next);
    return next;
  };

  const download = async (h) => {
    const k = hex(h);
    if (!cvm.FC.has(k)) cvm.FC.set(k, await cvm.download_file(h));
    return cvm.FC.get(k);
  };

  const upload = async (file) =>
    unhex((await (await fetch(`${apiBase}/api/upload`, {
      method: "POST",
      body: file,
    })).json()).data.hash);

  const userGet = async (keyHash) =>
    unhex((await (await fetch(`${apiBase}/api/user/get/${hex(cvm.USER)}/${hex(keyHash)}`)).json()).data.value);

  const userSet = async (keyHash, fileHash) =>
    fetch(`${apiBase}/api/user/set/${hex(cvm.USER)}/${hex(keyHash)}/${hex(fileHash)}`, {
      method: "POST",
    });

  cvm.gethashhashfile = async (keyHash) => {
    const k = hex(keyHash);

    if (cvm.OV.has(k)) return cvm.OV.get(k);

    if (!cvm.HC.has(k)) {
      let h;

      if (cvm.USER) {
        try {
          h = await userGet(keyHash);
        } catch {
          h = await cvm.getfirstchild(keyHash);
        }
      } else {
        h = await cvm.getfirstchild(keyHash);
      }

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

  cvm.user = (userId) => {
    cvm.USER = hex(userId);
    cvm.HC.clear();
  };

  cvm.data = () =>
    cvm.PTR.buf.subarray(cvm.PTR.off + 36, cvm.PTR.off + 36 + dlen());

  cvm.buildBlock = (xs) => {
    xs = xs.map(item);
    const b = new Uint8Array(xs.reduce((n, x) => n + 36 + x.data.length, 32));

    let o = 0;

    for (const x of xs) {
      b.set(unhex(x.hash), o);
      o += 32;

      w32(b, o, x.data.length);
      o += 4;

      b.set(x.data, o);
      o += x.data.length;
    }

    return b;
  };

  cvm.parseBlock = (b) => {
    const xs = [];

    for (let o = 0; !zhash(b, o);) {
      const n = u32(b, o + 32);
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
    cvm.ROOT = file;
    cvm.PTR = { buf: file, off: 0 };
    cvm.override(await cvm.sha256("HTMLJSstart"), file);
  };

  cvm.persistRoot = async () => {
    if (!cvm.ROOT) return;
    cvm.PROG = cvm.parseBlock(cvm.ROOT).map(item);
    cvm.override(await cvm.sha256("HTMLJSstart"), cvm.ROOT);

    try {
      await cvm.Modify_override();
    } catch (err) {
      console.warn("CVM persistRoot failed", err);
    }
  };

  cvm.enterBlock = async (block) => {
    block = bytes(block);
    if (!block.length) block = new Uint8Array(32);

    cvm.ST.push({
      buf: cvm.PTR.buf,
      off: cvm.PTR.off,
    });

    cvm.PTR = {
      buf: block,
      off: 0,
    };

    return cvm.executeBlock();
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
})();


// ============================================================
// 文件浏览器 + 节点可视化编辑器 + 节点内参数编辑器
// ============================================================
if (!CVM.__ui) {
  CVM.__ui = true;

  const cvm = CVM;
  const decoder = new TextDecoder();
  const encoder = new TextEncoder();
  const zeroHash = "00".repeat(32);
  const zeroBlock = new Uint8Array(32);
  const emptyData = new Uint8Array();

  const unhex = (hex) =>
    new Uint8Array(hex.match(/../g).map((part) => parseInt(part, 16)));

  const esc = (text) => String(text ?? "").replace(/[&<>"']/g, (ch) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
  })[ch]);

  const bytes = (x) => x instanceof Uint8Array ? x :
    x instanceof ArrayBuffer ? new Uint8Array(x) :
    ArrayBuffer.isView(x) ? new Uint8Array(x.buffer, x.byteOffset, x.byteLength) :
    encoder.encode(String(x ?? ""));

  const u32 = (b, o) =>
    new DataView(b.buffer, b.byteOffset, b.byteLength).getUint32(o, true);

  const w32 = (n) => {
    const b = new Uint8Array(4);
    new DataView(b.buffer).setUint32(0, n >>> 0, true);
    return b;
  };

  const concat = (...xs) => {
    xs = xs.map(bytes);
    const out = new Uint8Array(xs.reduce((n, x) => n + x.length, 0));
    let o = 0;
    for (const x of xs) {
      out.set(x, o);
      o += x.length;
    }
    return out;
  };

  const asItem = (value) =>
    typeof value === "string"
      ? { hash: value, data: emptyData }
      : {
          hash: typeof value.hash === "string" ? value.hash : cvm.hex(value.hash),
          data: value.data ?? emptyData,
        };

  const children = async (hash) =>
    (await (await fetch(`${apiBase}/api/children/${hash}`)).json()).data.children;

  const tagOf = async (hash) => {
    try {
      const b = await cvm.download_file(unhex(hash));
      const text = decoder.decode(b);
      return (text || hash).trim();
    } catch {
      return hash;
    }
  };

  const label = async (hash) => {
    const tag = await tagOf(hash);
    return tag.slice(0, 80);
  };

  const metaCache = new Map();

  const loadMeta = async (tag) => {
    if (metaCache.has(tag)) return metaCache.get(tag);

    const getText = async (name) => {
      try {
        return decoder.decode(await cvm.gethashhashfile(await cvm.sha256(name)));
      } catch {
        return "";
      }
    };

    const meta = {
      svg: await getText(`${tag}.svg`),
      describe: await getText(`${tag}.describe`),
      metersupport: await getText(`${tag}.metersupport`),
    };

    metaCache.set(tag, meta);
    return meta;
  };

  const parseBlockSafe = (data) => {
    try {
      return cvm.parseBlock(data && data.length ? data : zeroBlock).map(asItem);
    } catch {
      return [];
    }
  };

  if (!cvm.PROG) {
    cvm.PROG = cvm.parseBlock(cvm.PTR.buf);
  }

  cvm.PROG = cvm.PROG.map(asItem);

  cvm.LIBS ??= {
    gsap: { url: "https://cdn.jsdelivr.net/npm/gsap@3.12.5/dist/gsap.min.js", global: "gsap" },
    anime: { url: "https://cdn.jsdelivr.net/npm/animejs@3.2.2/lib/anime.min.js", global: "anime" },
    matter: { url: "https://cdn.jsdelivr.net/npm/matter-js@0.20.0/build/matter.min.js", global: "Matter" },
    planck: { url: "https://cdn.jsdelivr.net/npm/planck-js@0.3.31/dist/planck.min.js", global: "planck" },
    pixi: { url: "https://cdn.jsdelivr.net/npm/pixi.js@8.8.1/dist/pixi.min.js", global: "PIXI" },
    phaser: { url: "https://cdn.jsdelivr.net/npm/phaser@3.87.0/dist/phaser.min.js", global: "Phaser" },
    babylon: { url: "https://cdn.jsdelivr.net/npm/babylonjs@7.42.0/babylon.min.js", global: "BABYLON" },
    konva: { url: "https://cdn.jsdelivr.net/npm/konva@9.3.18/konva.min.js", global: "Konva" },
    fabric: { url: "https://cdn.jsdelivr.net/npm/fabric@5.5.2/dist/fabric.min.js", global: "fabric" },
    paper: { url: "https://cdn.jsdelivr.net/npm/paper@0.12.18/dist/paper-full.min.js", global: "paper" },
    two: { url: "https://cdn.jsdelivr.net/npm/two.js@0.8.17/build/two.min.js", global: "Two" },
    p5: { url: "https://cdn.jsdelivr.net/npm/p5@1.11.2/lib/p5.min.js", global: "p5" },
    d3: { url: "https://cdn.jsdelivr.net/npm/d3@7.9.0/dist/d3.min.js", global: "d3" },
    cytoscape: { url: "https://cdn.jsdelivr.net/npm/cytoscape@3.30.4/dist/cytoscape.min.js", global: "cytoscape" },
    rough: { url: "https://cdn.jsdelivr.net/npm/roughjs@4.6.6/bundled/rough.min.js", global: "rough" },
    three: { module: true, url: "https://cdn.jsdelivr.net/npm/three@0.171.0/build/three.module.js" },
    cannon: { module: true, url: "https://cdn.jsdelivr.net/npm/cannon-es@0.20.0/dist/cannon-es.js" },
  };

  cvm.LIB_CACHE ??= new Map();

  cvm.lib = async (name) => {
    if (cvm.LIB_CACHE.has(name)) return cvm.LIB_CACHE.get(name);

    const spec = cvm.LIBS[name];
    if (!spec) throw new Error(`unknown lib: ${name}`);

    const promise = spec.module
      ? import(spec.url)
      : new Promise((resolve, reject) => {
          if (spec.global && globalThis[spec.global]) {
            resolve(globalThis[spec.global]);
            return;
          }

          const script = document.createElement("script");
          script.src = spec.url;
          script.onload = () => resolve(spec.global ? globalThis[spec.global] : true);
          script.onerror = reject;
          document.head.appendChild(script);
        });

    cvm.LIB_CACHE.set(name, promise);
    return promise;
  };

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
      box-sizing: border-box;
    }
    .cvm-graph-panel {
      width: min(980px, calc(100vw - 360px));
      height: min(78vh, 720px);
      max-height: none;
      overflow: hidden;
    }
    .cvm-head {
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 8px;
      margin-bottom: 8px;
      cursor: move;
      user-select: none;
    }
    .cvm-head button {
      color: #ddd;
      background: #333;
      border: 1px solid #666;
      padding: 2px 8px;
      font: inherit;
      cursor: pointer;
    }
    .cvm-row {
      margin: 4px 0;
      padding: 4px 6px;
      background: #333;
      overflow: hidden;
      white-space: nowrap;
      text-overflow: ellipsis;
      cursor: pointer;
    }
    .cvm-row:hover {
      background: #3f4a5a;
    }
    .cvm-path {
      margin-bottom: 6px;
      color: #aaa;
      word-break: break-all;
    }
    .cvm-graph {
      position: relative;
      height: calc(100% - 46px);
      min-height: 380px;
      overflow: auto;
      background:
        linear-gradient(#2b2b2b 1px, transparent 1px),
        linear-gradient(90deg, #2b2b2b 1px, transparent 1px);
      background-size: 24px 24px;
      border: 1px solid #444;
      box-sizing: border-box;
    }
    .cvm-graph svg.cvm-lines {
      position: absolute;
      left: 0;
      top: 0;
      pointer-events: none;
      overflow: visible;
    }
    .cvm-node {
      position: absolute;
      width: 270px;
      height: 380px;
      padding: 7px 8px;
      box-sizing: border-box;
      color: #eee;
      background: #303642;
      border: 1px solid #6b7a94;
      box-shadow: 0 3px 10px rgba(0,0,0,.28);
      cursor: grab;
      user-select: none;
      overflow: hidden;
    }
    .cvm-node:hover {
      border-color: #89b4fa;
      background: #364052;
    }
    .cvm-node.dragging {
      opacity: .55;
    }
    .cvm-node.drop-before {
      border-left: 4px solid #a6e3a1;
    }
    .cvm-node.drop-after {
      border-right: 4px solid #a6e3a1;
    }
    .cvm-node-main {
      display: flex;
      align-items: center;
      gap: 7px;
    }
    .cvm-node-icon {
      width: 28px;
      height: 28px;
      flex: none;
      display: grid;
      place-items: center;
      color: #89b4fa;
    }
    .cvm-node-icon svg {
      width: 28px;
      height: 28px;
      display: block;
    }
    .cvm-node-title {
      min-width: 0;
      font-weight: bold;
      overflow: hidden;
      white-space: nowrap;
      text-overflow: ellipsis;
    }
    .cvm-node-meta {
      margin-top: 5px;
      color: #aaa;
      overflow: hidden;
      white-space: nowrap;
      text-overflow: ellipsis;
    }
    .cvm-node-data {
      margin-top: 3px;
      color: #a6e3a1;
      overflow: hidden;
      white-space: nowrap;
      text-overflow: ellipsis;
    }
    .cvm-node-editor {
      margin-top: 8px;
      padding-top: 8px;
      height: 266px;
      overflow: auto;
      border-top: 1px solid #58657a;
      cursor: default;
      user-select: text;
    }
    .cvm-node-editor input,
    .cvm-node-editor textarea,
    .cvm-mini-editor input,
    .cvm-mini-editor textarea {
      user-select: text;
    }
    .cvm-add-zone {
      position: absolute;
      left: 24px;
      top: 24px;
      right: 24px;
      bottom: 24px;
      display: none;
      place-items: center;
      color: #bbb;
      border: 1px dashed #777;
      background: rgba(34,34,34,.72);
      pointer-events: none;
    }
    .cvm-graph.drag-target .cvm-add-zone {
      display: grid;
    }
    .cvm-form-row {
      margin: 8px 0;
    }
    .cvm-form-row label {
      display: block;
      margin-bottom: 3px;
      color: #aaa;
    }
    .cvm-form-row input,
    .cvm-form-row textarea {
      width: 100%;
      box-sizing: border-box;
      color: #eee;
      background: #151515;
      border: 1px solid #555;
      padding: 5px;
      font: inherit;
    }
    .cvm-form-row input[type="checkbox"] {
      width: auto;
      vertical-align: middle;
    }
    .cvm-inline-program {
      min-height: 88px;
      max-height: 192px;
      overflow: auto;
      padding: 6px;
      background: #181818;
      border: 1px solid #444;
    }
    .cvm-mini-node {
      display: block;
      margin: 5px 0;
      padding: 6px;
      color: #eee;
      background: #333b4a;
      border: 1px solid #58657a;
      cursor: grab;
    }
    .cvm-mini-node:hover {
      border-color: #89b4fa;
    }
    .cvm-mini-node.drop-before {
      border-top: 3px solid #a6e3a1;
    }
    .cvm-mini-node.drop-after {
      border-bottom: 3px solid #a6e3a1;
    }
    .cvm-mini-main {
      display: flex;
      align-items: center;
      gap: 6px;
    }
    .cvm-mini-title {
      flex: 1;
      min-width: 0;
      overflow: hidden;
      white-space: nowrap;
      text-overflow: ellipsis;
    }
    .cvm-mini-remove {
      color: #f38ba8;
      cursor: pointer;
      padding: 0 4px;
    }
    .cvm-mini-editor {
      margin-top: 6px;
      padding-top: 6px;
      border-top: 1px solid #58657a;
      cursor: default;
      user-select: text;
    }
    .cvm-no-param {
      color: #888;
      padding: 4px 0;
    }
    .cvm-state {
      color: #a6e3a1;
    }
    .cvm-danger {
      color: #f38ba8 !important;
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
    .cvm-meter-card {
      padding: 8px;
      color: #f4f7ff;
      background: linear-gradient(135deg, #202633, #2d3340);
      border: 1px solid #7aa2f7;
      box-shadow: inset 0 0 0 1px rgba(255,255,255,.04), 0 0 18px rgba(122,162,247,.18);
    }
    .cvm-meter-title {
      margin-bottom: 8px;
      color: #89b4fa;
      font-weight: bold;
    }
    .cvm-meter-gauge {
      height: 12px;
      margin: 6px 0 10px;
      overflow: hidden;
      background: #111827;
      border: 1px solid #445;
    }
    .cvm-meter-fill {
      width: 0;
      height: 100%;
      background: linear-gradient(90deg, #a6e3a1, #89dceb, #f9e2af);
    }
    .cvm-meter-canvas {
      width: 100%;
      height: 92px;
      margin: 6px 0 10px;
      overflow: hidden;
      background: #111827;
      border: 1px solid #445;
    }
    .cvm-meter-button {
      width: 100%;
      margin-top: 6px;
      color: #111;
      background: #89dceb;
      border: 0;
      padding: 6px;
      font: bold 12px monospace;
      cursor: pointer;
    }
    .cvm-meter-pill {
      display: inline-block;
      margin: 2px 4px 2px 0;
      padding: 2px 6px;
      color: #111;
      background: #a6e3a1;
      border-radius: 999px;
    }

    .cvm-graph.cvm-world-stage {
      background: transparent;
      border-color: rgba(122,162,247,.32);
      box-shadow: inset 0 0 0 1px rgba(255,255,255,.03), 0 0 38px rgba(137,180,250,.08);
      --cvm-pan-x: 0px;
      --cvm-pan-y: 0px;
    }
    .cvm-graph.cvm-world-stage svg.cvm-lines,
    .cvm-graph.cvm-world-stage > .cvm-node {
      transform: translate(var(--cvm-pan-x), var(--cvm-pan-y));
      transform-origin: 0 0;
    }
    .cvm-root-node {
      position: absolute;
      left: 24px;
      top: 20px;
      z-index: 4;
      width: 260px;
      min-height: 86px;
      padding: 10px 12px;
      box-sizing: border-box;
      color: #eaf2ff;
      background: rgba(17,24,39,.56);
      border: 1px solid rgba(137,180,250,.72);
      box-shadow: 0 0 24px rgba(137,180,250,.16);
      backdrop-filter: blur(8px);
      cursor: grab;
      user-select: none;
      transform: translate(var(--cvm-pan-x), var(--cvm-pan-y));
    }
    .cvm-root-node:active {
      cursor: grabbing;
    }
    .cvm-root-title {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 8px;
      font-weight: bold;
      color: #89dceb;
    }
    .cvm-root-sub {
      margin-top: 7px;
      color: #cdd6f4;
      opacity: .82;
      white-space: normal;
    }
    .cvm-root-meter {
      height: 5px;
      margin-top: 9px;
      overflow: hidden;
      background: rgba(255,255,255,.1);
    }
    .cvm-root-meter > i {
      display: block;
      height: 100%;
      width: 100%;
      background: linear-gradient(90deg, #89dceb, #a6e3a1, #f9e2af);
    }
    .cvm-editor-actions {
      display: inline-flex;
      gap: 6px;
      margin-left: auto;
    }
    .cvm-editor-actions button {
      color: #ddd;
      background: #333;
      border: 1px solid #666;
      padding: 2px 8px;
      font: inherit;
      cursor: pointer;
    }
    .cvm-forge {
      position: fixed;
      right: 24px;
      bottom: 24px;
      z-index: 100000;
      width: min(680px, calc(100vw - 48px));
      max-height: min(82vh, 760px);
      overflow: auto;
      box-sizing: border-box;
      color: #e7ecff;
      background: rgba(18,22,31,.94);
      border: 1px solid rgba(137,180,250,.62);
      box-shadow: 0 16px 70px rgba(0,0,0,.45);
      font: 12px/1.45 monospace;
    }
    .cvm-forge-head {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 8px;
      padding: 9px 10px;
      border-bottom: 1px solid rgba(137,180,250,.22);
      cursor: move;
      user-select: none;
    }
    .cvm-forge-body {
      padding: 10px;
    }
    .cvm-forge-grid {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 8px;
    }
    .cvm-forge label {
      display: block;
      margin: 8px 0 3px;
      color: #bac2de;
    }
    .cvm-forge input,
    .cvm-forge textarea {
      width: 100%;
      box-sizing: border-box;
      color: #f4f7ff;
      background: #10141f;
      border: 1px solid #44506a;
      padding: 6px;
      font: inherit;
    }
    .cvm-forge textarea {
      min-height: 116px;
      resize: vertical;
    }
    .cvm-forge .cvm-code {
      min-height: 210px;
    }
    .cvm-forge-actions {
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
      margin-top: 10px;
    }
    .cvm-forge-actions button,
    .cvm-forge-head button {
      color: #111827;
      background: #89dceb;
      border: 0;
      padding: 6px 10px;
      font: bold 12px monospace;
      cursor: pointer;
    }
    .cvm-forge-actions button:hover,
    .cvm-forge-head button:hover {
      background: #a6e3a1;
    }
    .cvm-forge-state {
      margin-top: 8px;
      color: #a6e3a1;
      word-break: break-all;
    }
    @media (max-width: 760px) {
      .cvm-forge-grid {
        grid-template-columns: 1fr;
      }
    }

  </style>`);

  const dragPanel = (panel, handle) => {
    let startX = 0;
    let startY = 0;
    let panelX = 0;
    let panelY = 0;
    let dragging = false;

    handle.onmousedown = (event) => {
      if (event.target.closest("button,textarea,input")) return;

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

  const makePanel = (title, action, style, extraClass = "") => {
    const panel = document.createElement("div");

    panel.className = `cvm-panel ${extraClass}`;
    panel.style.cssText = style;
    panel.innerHTML = `
      <div class="cvm-head">
        <b>${esc(title)}</b>
        <button>${esc(action)}</button>
      </div>
      <div class="cvm-path"></div>
      <div class="cvm-list"></div>
    `;

    document.body.appendChild(panel);
    dragPanel(panel, panel.querySelector(".cvm-head"));

    return {
      panel,
      button: panel.querySelector("button"),
      path: panel.querySelector(".cvm-path"),
      list: panel.querySelector(".cvm-list"),
    };
  };

  const browser = makePanel("文件浏览器", "上级", "left:16px;top:16px");
  const editor = makePanel(
    "节点可视化编辑器 HTMLJSstart",
    "登录",
    "right:16px;top:16px",
    "cvm-graph-panel"
  );

  editor.path.textContent = "当前程序";
  editor.list.className = "cvm-graph";
  editor.list.innerHTML = `
    <svg class="cvm-lines"></svg>
    <div class="cvm-add-zone">拖入文件节点</div>
  `;

  const graph = editor.list;
  const svg = graph.querySelector("svg");


  (() => {
    if (cvm.__editorForge) return;
    cvm.__editorForge = true;

    graph.classList.add("cvm-world-stage");

    let panX = 0;
    let panY = 0;
    let panDrag = null;

    const setPan = () => {
      graph.style.setProperty("--cvm-pan-x", `${panX}px`);
      graph.style.setProperty("--cvm-pan-y", `${panY}px`);
    };

    const rootNode = document.createElement("div");
    rootNode.className = "cvm-root-node";
    rootNode.innerHTML = `
      <div class="cvm-root-title">
        <span>HTMLJSstart</span>
        <span class="cvm-root-count">0 nodes</span>
      </div>
      <div class="cvm-root-sub">public program root</div>
      <div class="cvm-root-meter"><i></i></div>
    `;
    graph.appendChild(rootNode);

    const updateRootNode = () => {
      const count = rootNode.querySelector(".cvm-root-count");
      if (count) count.textContent = `${cvm.PROG?.length || 0} nodes`;
    };

    rootNode.onmousedown = (event) => {
      if (event.target.closest("button,input,textarea")) return;

      panDrag = {
        x: event.clientX,
        y: event.clientY,
        panX,
        panY,
      };

      event.preventDefault();
    };

    graph.addEventListener("mousedown", (event) => {
      if (event.target !== graph) return;

      panDrag = {
        x: event.clientX,
        y: event.clientY,
        panX,
        panY,
      };

      event.preventDefault();
    });

    addEventListener("mousemove", (event) => {
      if (!panDrag) return;

      panX = panDrag.panX + event.clientX - panDrag.x;
      panY = panDrag.panY + event.clientY - panDrag.y;
      setPan();
    });

    addEventListener("mouseup", () => {
      panDrag = null;
    });

    setInterval(updateRootNode, 500);
    updateRootNode();

    const uploadPublicFile = async (name, data) => {
      if (!cvm.USER) {
        const id = prompt("user id");
        if (!id) throw new Error("need user id");
        cvm.user(id.trim().toLowerCase());
      }

      data = bytes(data);
      const nameHash = await cvm.sha256(name);
      const fileHash = await cvm.sha256(data);

      await fetch(`${apiBase}/api/upload`, {
        method: "POST",
        body: encoder.encode(name),
      });

      const uploaded = await (await fetch(`${apiBase}/api/upload`, {
        method: "POST",
        body: data,
      })).json();

      if (!uploaded.ok) throw new Error(uploaded.error || "upload failed");

      await fetch(`${apiBase}/api/edge/${cvm.hex(nameHash)}/${uploaded.data.hash}`, {
        method: "POST",
      });

      await fetch(`${apiBase}/api/vote/${cvm.USER}/${cvm.hex(nameHash)}/${uploaded.data.hash}`, {
        method: "POST",
      });

      return {
        name,
        nameHash: cvm.hex(nameHash),
        fileHash: uploaded.data.hash,
        directHash: cvm.hex(fileHash),
      };
    };

    const publishRoot = async (tag) => {
      const tagHash = await cvm.sha256(tag);

      await fetch(`${apiBase}/api/edge/${zeroHash}/${cvm.hex(tagHash)}`, {
        method: "POST",
      });

      await fetch(`${apiBase}/api/vote/${cvm.USER}/${zeroHash}/${cvm.hex(tagHash)}`, {
        method: "POST",
      });
    };

    const defaultModuleSource = () => `{
  const cvm = CVM;

  // 零参数模块：从 CVM.world / CVM.std 读取状态，执行一个动作。
  cvm.world ??= {};

  return cvm.resume();
}
`;

    const defaultMeterSupport = () => `async ({ cvm, body, api }) => {
  body.innerHTML = \`
    <div class="cvm-meter-card">
      <div class="cvm-meter-title">ZERO PARAMETER MODULE</div>
      <div class="cvm-no-param">这个模块不携带节点参数。</div>
    </div>
  \`;
}
`;

    const defaultSvg = () => `<svg viewBox="0 0 64 64" xmlns="http://www.w3.org/2000/svg">
  <rect x="9" y="9" width="46" height="46" rx="7" fill="#111827" stroke="#89dceb" stroke-width="4"/>
  <path d="M20 34h24M32 22v24" stroke="#a6e3a1" stroke-width="6" stroke-linecap="round"/>
</svg>`;

    const openForge = () => {
      let forge = document.querySelector(".cvm-forge");

      if (forge) {
        forge.style.display = "";
        return;
      }

      forge = document.createElement("div");
      forge.className = "cvm-forge";
      forge.innerHTML = `
        <div class="cvm-forge-head">
          <b>MODULE FORGE</b>
          <button type="button" class="cvm-close">关闭</button>
        </div>
        <div class="cvm-forge-body">
          <label>模块 tag</label>
          <input class="cvm-tag" placeholder="myModule">

          <label>执行 JS</label>
          <textarea class="cvm-source cvm-code"></textarea>

          <div class="cvm-forge-grid">
            <div>
              <label>describe</label>
              <textarea class="cvm-desc"></textarea>
            </div>
            <div>
              <label>svg</label>
              <textarea class="cvm-svg"></textarea>
            </div>
          </div>

          <label>metersupport</label>
          <textarea class="cvm-meter"></textarea>

          <div class="cvm-forge-actions">
            <button type="button" class="cvm-publish">发布到根目录</button>
            <button type="button" class="cvm-publish-add">发布并加入当前程序</button>
            <button type="button" class="cvm-template">零参数模板</button>
          </div>

          <div class="cvm-forge-state">ready</div>
        </div>
      `;

      document.body.appendChild(forge);
      dragPanel(forge, forge.querySelector(".cvm-forge-head"));

      const tagInput = forge.querySelector(".cvm-tag");
      const sourceInput = forge.querySelector(".cvm-source");
      const descInput = forge.querySelector(".cvm-desc");
      const svgInput = forge.querySelector(".cvm-svg");
      const meterInput = forge.querySelector(".cvm-meter");
      const state = forge.querySelector(".cvm-forge-state");

      sourceInput.value = defaultModuleSource();
      descInput.value = "零参数公开模块。";
      svgInput.value = defaultSvg();
      meterInput.value = defaultMeterSupport();

      forge.querySelector(".cvm-close").onclick = () => {
        forge.style.display = "none";
      };

      forge.querySelector(".cvm-template").onclick = () => {
        sourceInput.value = defaultModuleSource();
        descInput.value = "零参数公开模块。";
        svgInput.value = defaultSvg();
        meterInput.value = defaultMeterSupport();
      };

      const publish = async (addToProgram) => {
        const tag = tagInput.value.trim();

        if (!/^[A-Za-z0-9_.:-]{1,64}$/.test(tag)) {
          state.textContent = "tag 只能使用 A-Z a-z 0-9 _ . : -，长度 1-64";
          return;
        }

        try {
          state.textContent = "publishing...";

          await uploadPublicFile(tag, sourceInput.value);
          await uploadPublicFile(`${tag}.describe`, descInput.value || "");
          await uploadPublicFile(`${tag}.svg`, svgInput.value || "");
          await uploadPublicFile(`${tag}.metersupport`, meterInput.value || "");

          await publishRoot(tag);

          metaCache.delete(tag);
          metaCache.delete(`${tag}.describe`);
          metaCache.delete(`${tag}.svg`);
          metaCache.delete(`${tag}.metersupport`);

          if (addToProgram) {
            cvm.PROG.push({
              hash: cvm.hex(await cvm.sha256(tag)),
              data: emptyData,
            });

            await saveNow();
          }

          await renderBrowser();
          await renderEditor();

          state.textContent = `published: ${tag}`;
        } catch (err) {
          console.warn("CVM publish failed", err);
          state.textContent = `failed: ${err.message || err}`;
        }
      };

      forge.querySelector(".cvm-publish").onclick = () => publish(false);
      forge.querySelector(".cvm-publish-add").onclick = () => publish(true);
    };

    const head = editor.panel.querySelector(".cvm-head");

    if (!head.querySelector(".cvm-editor-actions")) {
      const actions = document.createElement("span");
      actions.className = "cvm-editor-actions";
      actions.innerHTML = `<button type="button" class="cvm-new-module">新建模块</button>`;
      head.insertBefore(actions, editor.button);
      actions.querySelector(".cvm-new-module").onclick = openForge;
    }

    cvm.openModuleForge = openForge;
    cvm.publishPublicFile = uploadPublicFile;
  })();


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

  let renderTimer = 0;
  let saveTimer = 0;

  const scheduleRender = () => {
    clearTimeout(renderTimer);
    renderTimer = setTimeout(renderEditor, 20);
  };

  const persistProgram = async () => {
    cvm.PROG = cvm.PROG.map(asItem);
    await cvm.setprog(cvm.PROG);

    try {
      await cvm.Modify_override();
    } catch (err) {
      console.warn("CVM autosave failed", err);
    }
  };

  const saveSoon = (rerender = false) => {
    clearTimeout(saveTimer);
    saveTimer = setTimeout(async () => {
      await persistProgram();
      if (rerender) scheduleRender();
    }, 180);
  };

  const saveNow = async () => {
    clearTimeout(saveTimer);
    await persistProgram();
    scheduleRender();
  };

  const moveItem = (prog, from, to) => {
    if (from < 0 || to < 0 || from === to) return;

    const it = prog.splice(from, 1)[0];
    const insertAt = from < to ? to - 1 : to;
    prog.splice(Math.max(0, Math.min(insertAt, prog.length)), 0, it);
  };

  const summarizeData = async (tag, data) => {
    if (tag === "setsize") {
      if (data.length < 4) return "bad setsize data";
      return `id=${decoder.decode(data.slice(0, -4))}, size=${u32(data, data.length - 4)}`;
    }

    if (tag === "getvar" || tag === "setvar") {
      return `id=${decoder.decode(data) || "(empty)"}`;
    }

    if (tag === "IF") {
      return `program nodes=${parseBlockSafe(data).length}`;
    }

    if (tag === "IFrerun") {
      return "if std bool then rerun";
    }

    if (tag === "Runonece" || tag === "Runonce") {
      return `enabled=${!!data[0]}, program nodes=${parseBlockSafe(data.slice(1)).length}`;
    }

    return data && data.length ? `data ${data.length} bytes` : "data: empty";
  };

  const adapterNames = new Set([
    "setsize",
    "getvar",
    "setvar",
    "IF",
    "IFrerun",
    "Runonece",
    "Runonce",
  ]);

  const meterSupportCache = new Map();

  async function renderInlineItemEditor(body, item, onChange) {
    const tag = await tagOf(item.hash);
    const meta = await loadMeta(tag);

    body.classList.add("cvm-inline-editor");

    body.innerHTML = `
      <div class="cvm-editor-body"></div>
      <div class="cvm-form-row">
        <span class="cvm-state">实时同步</span>
      </div>
    `;

    const editorBody = body.querySelector(".cvm-editor-body");
    const state = body.querySelector(".cvm-state");

    const commit = async () => {
      state.textContent = "同步中";
      await onChange();

      clearTimeout(commit.__timer);
      commit.__timer = setTimeout(() => {
        state.textContent = "实时同步";
      }, 240);
    };

    const meterSource = String(meta.metersupport || "").trim();

    const baseApi = {
      esc,
      bytes,
      concat,
      u32,
      w32,
      unhex,
      decoder,
      encoder,
      emptyData,
      zeroBlock,
      parseBlockSafe,
      renderInlineProgram,
      commit,
      lib: cvm.lib,
    };

    if (meterSource) {
      try {
        if (!meterSupportCache.has(tag)) {
          meterSupportCache.set(tag, eval(`(${meterSource})`));
        }

        await meterSupportCache.get(tag)({
          cvm,
          tag,
          item,
          body: editorBody,
          state,
          api: baseApi,
        });
      } catch (err) {
        console.warn(`CVM metersupport failed: ${tag}`, err);
        editorBody.innerHTML = `<div class="cvm-no-param cvm-danger">metersupport 加载失败</div>`;
      }

      return;
    }

    if (!adapterNames.has(tag)) {
      editorBody.innerHTML = `<div class="cvm-no-param">此节点无专用参数。</div>`;
      return;
    }

    if (tag === "setsize") {
      const id = item.data.length >= 4 ? decoder.decode(item.data.slice(0, -4)) : "";
      const size = item.data.length >= 4 ? u32(item.data, item.data.length - 4) : 0;

      editorBody.innerHTML = `
        <div class="cvm-form-row">
          <label>变量 id</label>
          <input class="cvm-id" value="${esc(id)}">
        </div>
        <div class="cvm-form-row">
          <label>变量大小 size</label>
          <input class="cvm-size" type="number" min="0" step="1" value="${size}">
        </div>
      `;

      const idInput = editorBody.querySelector(".cvm-id");
      const sizeInput = editorBody.querySelector(".cvm-size");

      const update = async () => {
        item.data = concat(
          encoder.encode(idInput.value),
          w32(Number(sizeInput.value) || 0)
        );

        await commit();
      };

      idInput.oninput = update;
      sizeInput.oninput = update;
      return;
    }

    if (tag === "getvar" || tag === "setvar") {
      editorBody.innerHTML = `
        <div class="cvm-form-row">
          <label>变量 id</label>
          <input class="cvm-id" value="${esc(decoder.decode(item.data || emptyData))}">
        </div>
      `;

      const idInput = editorBody.querySelector(".cvm-id");

      idInput.oninput = async () => {
        item.data = encoder.encode(idInput.value);
        await commit();
      };

      return;
    }

    if (tag === "IFrerun") {
      editorBody.innerHTML = `
        <div class="cvm-no-param">
          无参数。运行时读取 std 第一个布尔值，为真则当前块重新执行。
        </div>
      `;

      return;
    }

    if (tag === "IF") {
      const nested = parseBlockSafe(item.data);

      editorBody.innerHTML = `
        <div class="cvm-form-row">
          <label>IF 内部程序</label>
          <div class="cvm-if-program"></div>
        </div>
      `;

      await renderInlineProgram(editorBody.querySelector(".cvm-if-program"), nested, async () => {
        item.data = cvm.buildBlock(nested);
        await commit();
      });

      return;
    }

    if (tag === "Runonece" || tag === "Runonce") {
      let enabled = !!item.data[0];
      const nested = parseBlockSafe((item.data || emptyData).slice(1));

      editorBody.innerHTML = `
        <div class="cvm-form-row">
          <label>
            <input class="cvm-enabled" type="checkbox" ${enabled ? "checked" : ""}>
            执行一次
          </label>
        </div>
        <div class="cvm-form-row">
          <label>Runonce 内部程序</label>
          <div class="cvm-run-program"></div>
        </div>
      `;

      const enabledInput = editorBody.querySelector(".cvm-enabled");

      const saveNested = async () => {
        enabled = !!enabledInput.checked;
        item.data = concat(
          new Uint8Array([enabled ? 1 : 0]),
          cvm.buildBlock(nested)
        );
        await commit();
      };

      enabledInput.onchange = saveNested;

      await renderInlineProgram(editorBody.querySelector(".cvm-run-program"), nested, saveNested);
    }
  }

  const renderInlineProgram = async (holder, prog, onChange) => {
    holder.querySelectorAll?.(".cvm-mini-editor").forEach((editor) => {
      editor.__cvmCleanup?.();
    });
    holder.innerHTML = "";
    holder.classList.add("cvm-inline-program");
    holder.__dragKey ??= `application/cvm-mini-index-${Math.random()}`;

    if (!prog.length) {
      const empty = document.createElement("div");
      empty.style.color = "#777";
      empty.textContent = "空程序。可从左侧文件浏览器拖入节点。";
      holder.appendChild(empty);
    }

    for (let index = 0; index < prog.length; index++) {
      const item = asItem(prog[index]);
      const tag = await tagOf(item.hash);
      const meta = await loadMeta(tag);

      const row = document.createElement("div");
      row.className = "cvm-mini-node";
      row.draggable = true;

      row.innerHTML = `
        <div class="cvm-mini-main">
          <div class="cvm-node-icon">${meta.svg || "◇"}</div>
          <div class="cvm-mini-title">${index}. ${esc(tag)}</div>
          <div class="cvm-mini-remove">x</div>
        </div>
        <div class="cvm-node-data">${esc(await summarizeData(tag, item.data || emptyData))}</div>
        <div class="cvm-mini-editor"></div>
      `;

      row.querySelector(".cvm-mini-remove").onclick = async (event) => {
        event.stopPropagation();
        prog.splice(index, 1);
        await onChange();
        await renderInlineProgram(holder, prog, onChange);
      };

      row.ondragstart = (event) => {
        if (event.target.closest("input,textarea,button,.cvm-mini-editor")) {
          event.preventDefault();
          return;
        }

        event.dataTransfer.effectAllowed = "move";
        event.dataTransfer.setData(holder.__dragKey, String(index));
      };

      row.ondragover = (event) => {
        event.preventDefault();
        event.stopPropagation();

        const rect = row.getBoundingClientRect();
        const before = event.clientY < rect.top + rect.height / 2;

        row.classList.toggle("drop-before", before);
        row.classList.toggle("drop-after", !before);
      };

      row.ondragleave = () => {
        row.classList.remove("drop-before", "drop-after");
      };

      row.ondrop = async (event) => {
        event.preventDefault();
        event.stopPropagation();
        row.classList.remove("drop-before", "drop-after");

        const miniIndex = event.dataTransfer.getData(holder.__dragKey);
        const incomingHash = event.dataTransfer.getData("text/plain");

        const rect = row.getBoundingClientRect();
        const before = event.clientY < rect.top + rect.height / 2;
        const target = before ? index : index + 1;

        if (miniIndex !== "") {
          moveItem(prog, Number(miniIndex), target);
        } else if (incomingHash) {
          prog.splice(target, 0, { hash: incomingHash, data: emptyData });
        }

        await onChange();
        await renderInlineProgram(holder, prog, onChange);
      };

      holder.appendChild(row);

      await renderInlineItemEditor(
        row.querySelector(".cvm-mini-editor"),
        item,
        async () => {
          prog[index] = item;
          await onChange();
        }
      );
    }

    holder.ondragover = (event) => {
      event.preventDefault();
      event.stopPropagation();
    };

    holder.ondrop = async (event) => {
      event.preventDefault();
      event.stopPropagation();

      const miniIndex = event.dataTransfer.getData(holder.__dragKey);
      const incomingHash = event.dataTransfer.getData("text/plain");

      if (miniIndex !== "") {
        moveItem(prog, Number(miniIndex), prog.length);
      } else if (incomingHash) {
        prog.push({ hash: incomingHash, data: emptyData });
      }

      await onChange();
      await renderInlineProgram(holder, prog, onChange);
    };
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

      row.ondragstart = (event) => {
        event.dataTransfer.effectAllowed = "copy";
        event.dataTransfer.setData("text/plain", child.hash);
      };

      row.onclick = () => {
        cvm.browserStack.push(child.hash);
        renderBrowser();
      };

      browser.list.appendChild(row);
    }
  }

  async function renderEditor() {
    graph.querySelectorAll(".cvm-node").forEach((node) => {
      node.querySelectorAll(".cvm-node-editor,.cvm-mini-editor").forEach((editor) => {
        editor.__cvmCleanup?.();
      });
      node.remove();
    });
    svg.innerHTML = "";

    const graphWidth = Math.max(graph.clientWidth, 260);
    const nodeW = 270;
    const nodeH = 380;
    const gapX = 56;
    const gapY = 56;
    const cols = Math.max(1, Math.floor((graphWidth - 48) / (nodeW + gapX)));
    const rows = Math.ceil(Math.max(1, cvm.PROG.length) / cols);
    const canvasW = Math.max(graphWidth, 48 + cols * (nodeW + gapX));
    const canvasH = Math.max(graph.clientHeight, 178 + rows * (nodeH + gapY));

    svg.setAttribute("width", String(canvasW));
    svg.setAttribute("height", String(canvasH));
    svg.style.width = `${canvasW}px`;
    svg.style.height = `${canvasH}px`;

    for (let index = 0; index < cvm.PROG.length; index++) {
      const item = asItem(cvm.PROG[index]);
      const tag = await tagOf(item.hash);
      const meta = await loadMeta(tag);
      const col = index % cols;
      const row = Math.floor(index / cols);
      const x = 24 + col * (nodeW + gapX);
      const y = 154 + row * (nodeH + gapY);

      const node = document.createElement("div");
      node.className = "cvm-node";
      node.draggable = true;
      node.style.left = `${x}px`;
      node.style.top = `${y}px`;

      node.innerHTML = `
        <div class="cvm-node-main">
          <div class="cvm-node-icon">${meta.svg || "◇"}</div>
          <div class="cvm-node-title">${index}. ${esc(tag)}</div>
        </div>
        <div class="cvm-node-meta">${esc(item.hash.slice(0, 16))}</div>
        <div class="cvm-node-data">${esc(await summarizeData(tag, item.data || emptyData))}</div>
        <div class="cvm-node-editor"></div>
      `;

      node.ondragstart = (event) => {
        if (event.target.closest("input,textarea,button,.cvm-node-editor")) {
          event.preventDefault();
          return;
        }

        node.classList.add("dragging");
        event.dataTransfer.effectAllowed = "move";
        event.dataTransfer.setData("application/cvm-index", String(index));
      };

      node.ondragend = () => {
        node.classList.remove("dragging", "drop-before", "drop-after");
      };

      node.ondragover = (event) => {
        event.preventDefault();
        event.stopPropagation();

        const rect = node.getBoundingClientRect();
        const before = event.clientX < rect.left + rect.width / 2;

        node.classList.toggle("drop-before", before);
        node.classList.toggle("drop-after", !before);
      };

      node.ondragleave = () => {
        node.classList.remove("drop-before", "drop-after");
      };

      node.ondrop = async (event) => {
        event.preventDefault();
        event.stopPropagation();
        node.classList.remove("drop-before", "drop-after");

        const incomingIndex = event.dataTransfer.getData("application/cvm-index");
        const incomingHash = event.dataTransfer.getData("text/plain");

        const rect = node.getBoundingClientRect();
        const before = event.clientX < rect.left + rect.width / 2;
        const target = before ? index : index + 1;

        if (incomingIndex !== "") {
          moveItem(cvm.PROG, Number(incomingIndex), target);
          await saveNow();
          return;
        }

        if (incomingHash) {
          cvm.PROG.splice(target, 0, { hash: incomingHash, data: emptyData });
          await saveNow();
        }
      };

      graph.appendChild(node);

      await renderInlineItemEditor(
        node.querySelector(".cvm-node-editor"),
        item,
        async () => {
          cvm.PROG[index] = item;
          saveSoon(false);
        }
      );

      if (index > 0) {
        const prevCol = (index - 1) % cols;
        const prevRow = Math.floor((index - 1) / cols);
        const x1 = 24 + prevCol * (nodeW + gapX) + nodeW;
        const y1 = 24 + prevRow * (nodeH + gapY) + nodeH / 2;
        const x2 = x;
        const y2 = y + nodeH / 2;

        const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
        const mid = Math.max(18, Math.abs(x2 - x1) / 2);

        path.setAttribute("d", `M ${x1} ${y1} C ${x1 + mid} ${y1}, ${x2 - mid} ${y2}, ${x2} ${y2}`);
        path.setAttribute("fill", "none");
        path.setAttribute("stroke", "#89b4fa");
        path.setAttribute("stroke-width", "2");

        svg.appendChild(path);
      }
    }
  }

  graph.ondragover = (event) => {
    if (event.target.closest(".cvm-node-editor,.cvm-mini-editor,.cvm-inline-program,.cvm-mini-node")) {
      return;
    }

    event.preventDefault();
    graph.classList.add("drag-target");
  };

  graph.ondragleave = (event) => {
    if (!graph.contains(event.relatedTarget)) {
      graph.classList.remove("drag-target");
    }
  };

  graph.ondrop = async (event) => {
    if (event.target.closest(".cvm-node-editor,.cvm-mini-editor,.cvm-inline-program,.cvm-mini-node")) {
      return;
    }

    event.preventDefault();
    graph.classList.remove("drag-target");

    const incomingIndex = event.dataTransfer.getData("application/cvm-index");
    const incomingHash = event.dataTransfer.getData("text/plain");

    if (incomingIndex !== "") {
      moveItem(cvm.PROG, Number(incomingIndex), cvm.PROG.length);
      await saveNow();
      return;
    }

    if (incomingHash) {
      cvm.PROG.push({ hash: incomingHash, data: emptyData });
      await saveNow();
    }
  };

  browser.button.onclick = () => {
    if (cvm.browserStack.length > 1) {
      cvm.browserStack.pop();
      renderBrowser();
    }
  };

  editor.button.onclick = async () => {
    const id = prompt("user id");
    if (!id) return;

    cvm.user(id.trim().toLowerCase());

    try {
      const file = await cvm.gethashhashfile(await cvm.sha256("HTMLJSstart"));
      cvm.PROG = cvm.parseBlock(file).map(asItem);
      cvm.ROOT = cvm.buildBlock(cvm.PROG);
      await renderEditor();
    } catch (err) {
      console.warn("CVM user program load failed", err);
    }
  };

  cvm.renderBrowser = renderBrowser;
  cvm.renderEditor = renderEditor;

  await renderBrowser();
  await renderEditor();
}


// ============================================================
// 持续入口
// ============================================================
{
  const cvm = CVM;
  cvm.PTR.buf = cvm.buildBlock(cvm.PROG);
  cvm.ROOT = cvm.PTR.buf;
  cvm.PTR.off = 0;
  await new Promise((r) => setTimeout(r, 60));
  return cvm.resume();
}

"""

# ==========================================
# 2. 基础控制与逻辑模块 (零参数)
# ==========================================
MODULES_JS = {
    "rerun": "CVM.PTR.off=0;return CVM.executeBlock();\n",
    "print": 'CVM.out("hello world");return CVM.resume();\n',
    "setsize": "{ const cvm = CVM; const d = cvm.data(); if (d.length >= 4) { const id = d.slice(0, d.length - 4); const size = new DataView(d.buffer, d.byteOffset + d.length - 4, 4).getUint32(0, true); cvm.setVarSize(id, size); } return cvm.resume(); }",
    "getvar": "{ const cvm = CVM; const id = cvm.data(); const value = cvm.getVar(id); cvm.stdReturn(value); return cvm.resume(); }",
    "setvar": "{ const cvm = CVM; const id = cvm.data(); const size = cvm.VSZ.get(cvm.varKey(id)) ?? 0; cvm.stdInput(); const value = cvm.stdRead(size); cvm.setVar(id, value); return cvm.resume(); }",
    "IF": "{ const cvm = CVM; const program = cvm.data(); if (!cvm.stdBool()) return cvm.resume(); return cvm.enterBlock(program); }",
    "IFrerun": "{ const cvm = CVM; if (cvm.stdBool()) { cvm.PTR.off = 0; return cvm.executeBlock(); } return cvm.resume(); }",
    "Runonece": "{ const cvm = CVM; const d = cvm.data(); if (!d.length || !d[0]) return cvm.resume(); d[0] = 0; await cvm.persistRoot(); return cvm.enterBlock(d.subarray(1)); }",
    "Runonce": "{ const cvm = CVM; const d = cvm.data(); if (!d.length || !d[0]) return cvm.resume(); d[0] = 0; await cvm.persistRoot(); return cvm.enterBlock(d.subarray(1)); }",
}

# ==========================================
# 3. 物理/游戏模块 (零参数，操作 CVM.world)
# ==========================================
PHYSICS_JS = {
    "physicsWorld": "{ const cvm = CVM; const Matter = await cvm.lib('matter'); cvm.world ??= {}; const physics = cvm.world.physics ??= {}; physics.defaults ??= { ball: { radius: 24, restitution: 0.86, frictionAir: 0.01, color: '#89dceb' }, gravity: { x: 0, y: 1 } }; if (!physics.engine) { physics.engine = Matter.Engine.create(); physics.engine.gravity.x = physics.defaults.gravity.x; physics.engine.gravity.y = physics.defaults.gravity.y; physics.bodies = new Map(); physics.bounds = []; } return cvm.resume(); }",
    "renderPhysics": "{ const cvm = CVM; const Matter = await cvm.lib('matter'); cvm.world ??= {}; const physics = cvm.world.physics ??= {}; if (!physics.engine) return cvm.resume(); let panel = document.getElementById('cvm-physics-stage'); if (!panel) { panel = document.createElement('div'); panel.id = 'cvm-physics-stage'; panel.style.cssText = 'position:fixed;left:16px;bottom:16px;z-index:99997;width:520px;height:300px;background:#111827;border:1px solid #7aa2f7;box-shadow:0 0 24px rgba(122,162,247,.22);overflow:hidden'; document.body.appendChild(panel); } const width = panel.clientWidth || 520, height = panel.clientHeight || 300; if (!physics.boundsReady) { const wallStyle = { fillStyle: '#293241', strokeStyle: '#7aa2f7', lineWidth: 1 }; physics.bounds = [Matter.Bodies.rectangle(width/2, height+10, width, 20, {isStatic:true, render:wallStyle}), Matter.Bodies.rectangle(width/2, -10, width, 20, {isStatic:true, render:wallStyle}), Matter.Bodies.rectangle(-10, height/2, 20, height, {isStatic:true, render:wallStyle}), Matter.Bodies.rectangle(width+10, height/2, 20, height, {isStatic:true, render:wallStyle})]; Matter.Composite.add(physics.engine.world, physics.bounds); physics.boundsReady = true; } if (!physics.render) { physics.render = Matter.Render.create({ element: panel, engine: physics.engine, options: { width, height, wireframes: false, background: '#111827', pixelRatio: window.devicePixelRatio || 1 } }); physics.runner = Matter.Runner.create(); Matter.Render.run(physics.render); Matter.Runner.run(physics.runner, physics.engine); } return cvm.resume(); }",
    "spawnBall": "{ const cvm = CVM; const Matter = await cvm.lib('matter'); cvm.world ??= {}; const physics = cvm.world.physics ??= {}; if (!physics.engine) return cvm.resume(); physics.bodies ??= new Map(); const cfg = physics.defaults.ball; const x = 80 + Math.random() * 340, y = 36 + Math.random() * 42; const ball = Matter.Bodies.circle(x, y, cfg.radius, { restitution: cfg.restitution, frictionAir: cfg.frictionAir, render: { fillStyle: cfg.color, strokeStyle: '#f4f7ff', lineWidth: 2 } }); Matter.Body.setVelocity(ball, { x: -5 + Math.random() * 10, y: -2 + Math.random() * 3 }); Matter.Composite.add(physics.engine.world, ball); physics.bodies.set(`ball:${Date.now()}:${Math.random()}`, ball); return cvm.resume(); }",
    "kickPhysics": "{ const cvm = CVM; const Matter = await cvm.lib('matter'); const bodies = cvm.world?.physics?.bodies; if (bodies) { for (const body of bodies.values()) { Matter.Body.applyForce(body, body.position, { x: (Math.random() - 0.5) * 0.08, y: -0.08 - Math.random() * 0.08 }); } } return cvm.resume(); }",
    "clearPhysics": "{ const cvm = CVM; const Matter = await cvm.lib('matter'); const physics = cvm.world?.physics; if (physics?.engine && physics?.bodies) { for (const body of physics.bodies.values()) { Matter.Composite.remove(physics.engine.world, body); } physics.bodies.clear(); } return cvm.resume(); }",
    "flipGravity": "{ const cvm = CVM; const physics = cvm.world?.physics; if (physics?.engine) { physics.engine.gravity.y = physics.engine.gravity.y >= 0 ? -1 : 1; physics.defaults ??= {}; physics.defaults.gravity = { x: physics.engine.gravity.x, y: physics.engine.gravity.y }; } return cvm.resume(); }",
}

# ==========================================
# 4. 元数据 (Meta)
# ==========================================
META = {
    "setsize.describe": "setsize 数据格式：id + uint32 little-endian size。",
    "getvar.describe": "getvar 数据格式：id。读取变量写入 std。",
    "setvar.describe": "setvar 数据格式：id。从 std 读取数据写入变量。",
    "IF.describe": "IF 数据格式：模块程序 block。",
    "IFrerun.describe": "IFrerun 无数据。std bool 为真则重新执行当前块。",
    "Runonece.describe": "Runonece 数据格式：bool + 模块程序 block。",
    "Runonce.describe": "Runonce 是 Runonece 的同义拼写。",
    "physicsWorld.describe": "零参数模块。创建 CVM.world.physics。",
    "renderPhysics.describe": "零参数模块。显示 Matter.js 物理舞台。",
    "spawnBall.describe": "零参数模块。生成一个物理小球。",
    "kickPhysics.describe": "零参数模块。给动态物体施加随机冲量。",
    "clearPhysics.describe": "零参数模块。清除动态物体。",
    "flipGravity.describe": "零参数模块。翻转重力方向。",
    
    "physicsWorld.metersupport": "async ({ cvm, body, api }) => { const { esc } = api; cvm.world ??= {}; const physics = cvm.world.physics ??= {}; physics.defaults ??= { ball: { radius: 24, restitution: 0.86, color: '#89dceb' }, gravity: { x: 0, y: 1 } }; const cfg = physics.defaults.ball; const g = physics.defaults.gravity; body.innerHTML = `<div class='cvm-meter-card'><div class='cvm-meter-title'>PHYSICS DEFAULTS</div><label>Radius: <input type='range' class='r' min='8' max='64' value='${cfg.radius}'> <span class='rv'>${cfg.radius}</span></label><label>Bounce: <input type='range' class='b' min='0' max='1' step='0.01' value='${cfg.restitution}'> <span class='bv'>${cfg.restitution}</span></label><label>Gravity Y: <input type='range' class='g' min='-2' max='2' step='0.1' value='${g.y}'> <span class='gv'>${g.y}</span></label><label>Color: <input type='color' class='c' value='${esc(cfg.color)}'></label></div>`; const sync = () => { cfg.radius = Number(body.querySelector('.r').value); cfg.restitution = Number(body.querySelector('.b').value); g.y = Number(body.querySelector('.g').value); cfg.color = body.querySelector('.c').value; body.querySelector('.rv').textContent = cfg.radius; body.querySelector('.bv').textContent = cfg.restitution; body.querySelector('.gv').textContent = g.y; if (physics.engine) physics.engine.gravity.y = g.y; }; body.querySelectorAll('input').forEach(i => i.oninput = sync); }",
}

# 补充基础 SVG
for name in ["setsize", "getvar", "setvar", "IF", "IFrerun", "Runonece", "Runonce", "physicsWorld", "renderPhysics", "spawnBall", "kickPhysics", "clearPhysics", "flipGravity"]:
    META[f"{name}.svg"] = f'<svg viewBox="0 0 64 64" xmlns="http://www.w3.org/2000/svg"><rect x="8" y="8" width="48" height="48" rx="8" fill="#111827" stroke="#89dceb" stroke-width="4"/><text x="32" y="40" font-size="24" fill="#a6e3a1" text-anchor="middle" font-family="monospace">{name[:4]}</text></svg>'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default=BASE_DEFAULT)
    ap.add_argument("--id", default="id.bin")
    args = ap.parse_args()

    api = API(args.base)
    user = get_or_create_id(api, args.id)

    print(f"\n服务器: {args.base}")
    print(f"用户ID: {user}\n")

    # 1. 上传核心启动文件
    put(api, user, "start", START_JS.encode())

    # 2. 上传基础逻辑模块
    for name, src in MODULES_JS.items():
        put(api, user, name, src.encode())

    # 3. 上传物理模块
    for name, src in PHYSICS_JS.items():
        put(api, user, name, src.encode())

    # 4. 上传元数据
    for name, src in META.items():
        put(api, user, name, src.encode())

    # 5. 构建并上传 HTMLJSstart 入口块
    put(api, user, "HTMLJSstart", block(["start", "rerun"]))

    # 6. 构建并上传模块集 (.bin)
    put(api, user, "base.bin", block(["setsize", "getvar", "setvar", "IF", "IFrerun", "Runonece"]))
    put(api, user, "physics.bin", block(["physicsWorld", "renderPhysics", "spawnBall", "kickPhysics", "clearPhysics", "flipGravity"]))

    # 7. 挂载到根目录 (Root)
    print("\n挂载根目录...")
    root_items = ["start", "HTMLJSstart", "base.bin", "physics.bin"] + list(MODULES_JS.keys()) + list(PHYSICS_JS.keys())
    for name in root_items:
        root(api, user, name)

    print("\n✅ 完整系统初始化完成！")
    print("打开浏览器访问服务器，即可进入 Stable Studio 编辑器。")

if __name__ == "__main__":
    main()
