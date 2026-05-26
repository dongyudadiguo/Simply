#!/usr/bin/env python3
# upload_cvm.py
import argparse
import hashlib
import json
import re
import struct
import sys
import urllib.error
import urllib.request
from pathlib import Path

BASE_DEFAULT = "http://124.221.146.23:9000"

ROOT_CHILDREN = ["Process control", "variable", "calculate", "time", "random", "draw"]
PROCESS_CHILDREN = ["IF", "for"]

START_JS = r'''
(async () => {
  const cvm = CVM;
  const enc = new TextEncoder();
  const dec = new TextDecoder();
  const API = typeof apiBase !== "undefined" ? apiBase : location.origin;

  const hex = (x) => typeof x === "string" ? x : cvm.hex(x);
  const unhex = (h) => new Uint8Array((h.match(/../g) || []).map((x) => parseInt(x, 16)));
  const keyOf = async (name) => hex(await cvm.sha256(name));
  const short = (h) => h.slice(0, 8) + "..." + h.slice(-6);
  const bytesText = (b) => dec.decode(b);
  const read32At = (buf, off) =>
    new DataView(buf.buffer, buf.byteOffset + off, 4).getUint32(0, true);

  const read32 = () =>
    new DataView(cvm.PTR.buf.buffer, cvm.PTR.buf.byteOffset)
      .getUint32(cvm.PTR.off, true);

  const readHash = (off) => cvm.PTR.buf.subarray(off, off + 32);

  cvm.FC ??= new Map();
  cvm.HC ??= new Map();
  cvm.OV ??= new Map();
  cvm.ST ??= [];

  const download = async (fileHash) => {
    const k = hex(fileHash);
    if (!cvm.FC.has(k)) cvm.FC.set(k, await cvm.download_file(fileHash));
    return cvm.FC.get(k);
  };

  const json = async (path, opt = {}) => {
    const r = await fetch(API + path, opt);
    const t = await r.text();
    let j;
    try { j = JSON.parse(t); } catch { throw new Error(t || r.statusText); }
    if (!r.ok || !j.ok) throw new Error(j.error || r.statusText);
    return j.data;
  };

  const upload = async (file) =>
    unhex((await json("/api/upload", { method: "POST", body: file })).hash);

  const childrenOf = async (keyHash) =>
    (await json("/api/children/" + hex(keyHash))).children || [];

  const addEdge = async (parent, child) =>
    json("/api/edge/" + hex(parent) + "/" + hex(child), { method: "POST" });

  const vote = async (user, parent, child) =>
    json("/api/vote/" + hex(user) + "/" + hex(parent) + "/" + hex(child), { method: "POST" });

  const userGet = async (keyHash) =>
    unhex((await json("/api/user/get/" + hex(cvm.USER) + "/" + hex(keyHash))).value);

  const userSet = async (keyHash, fileHash) =>
    json("/api/user/set/" + hex(cvm.USER) + "/" + hex(keyHash) + "/" + hex(fileHash), { method: "POST" });

  cvm.gethashhashfile = async (keyHash) => {
    const k = hex(keyHash);

    if (cvm.OV.has(k)) return cvm.OV.get(k);

    if (!cvm.HC.has(k)) {
      let fileHash;
      if (cvm.USER) {
        try { fileHash = await userGet(keyHash); }
        catch { fileHash = await cvm.getfirstchild(keyHash); }
      } else {
        fileHash = await cvm.getfirstchild(keyHash);
      }
      cvm.HC.set(k, fileHash);
    }

    return download(cvm.HC.get(k));
  };

  cvm.Modify_override = async () => {
    for (const [keyHex, file] of cvm.OV) {
      const fileHash = await upload(file);
      if (cvm.USER) await userSet(unhex(keyHex), fileHash);
      cvm.HC.set(keyHex, fileHash);
      cvm.FC.set(hex(fileHash), file);
    }
    cvm.OV.clear();
  };

  cvm.override = (keyHash, file) => cvm.OV.set(hex(keyHash), file);

  cvm.user = (userId) => {
    cvm.USER = hex(userId).trim();
    cvm.HC.clear();
    localStorage.cvmUser = cvm.USER;
  };

  cvm.executeBlock = async () => {
    for (;;) {
      const file = await cvm.gethashhashfile(readHash(cvm.PTR.off + 4));

      if (file[0]) return cvm.execute_call(dec.decode(file));

      await cvm.Modify_override();

      cvm.ST.push({ buf: cvm.PTR.buf, off: cvm.PTR.off });
      cvm.PTR = { buf: file, off: 0 };
    }
  };

  cvm.resume = async () => {
    cvm.PTR.off += 36;
    for (let n; n = read32(); cvm.PTR.off += 4 + n);
    return cvm.executeBlock();
  };

  const names = [
    "HTMLJSstart", "HTMLJSroot", "start", "continue",
    "Process control", "variable", "calculate", "time", "random", "draw",
    "IF", "for"
  ];

  const nameByHash = new Map();
  for (const n of names) nameByHash.set(await keyOf(n), n);

  const style = document.createElement("style");
  style.textContent = `
    *{box-sizing:border-box}
    html,body{margin:0;width:100%;height:100%;overflow:hidden;background:#070812;color:#f5f7ff;font:14px/1.4 ui-sans-serif,system-ui,-apple-system,Segoe UI}
    #cvmApp{position:fixed;inset:0;background:radial-gradient(circle at 30% 20%,#1c315f 0,#070812 38%,#05050a 100%)}
    #space{position:absolute;inset:0;width:100%;height:100%;cursor:grab}
    #space:active{cursor:grabbing}
    .bar{position:absolute;left:16px;right:16px;top:14px;height:52px;display:flex;align-items:center;gap:10px;padding:8px 10px;border:1px solid #314064;background:#090d18d9;backdrop-filter:blur(14px);border-radius:8px;box-shadow:0 12px 40px #0008}
    .brand{font-weight:800;font-size:17px;letter-spacing:0;color:#fff;white-space:nowrap}
    .pill{height:34px;border:1px solid #3e4c74;background:#11182a;color:#e9eeff;border-radius:7px;padding:0 11px;font-weight:650}
    .pill:hover{border-color:#7be3ff;background:#16233b}
    .hot{background:#f5c84b;color:#171102;border-color:#ffe08a}
    .ok{background:#41e39a;color:#021810;border-color:#83ffc6}
    input,textarea,select{border:1px solid #3d4a70;background:#080b14;color:#f6f8ff;border-radius:7px;outline:none}
    input{height:34px;padding:0 10px}
    textarea{width:100%;height:240px;padding:10px;resize:none;font:12px/1.45 ui-monospace,SFMono-Regular,Consolas,monospace}
    .left,.right{position:absolute;top:80px;bottom:16px;width:280px;border:1px solid #2d3b62;background:#080c17d9;backdrop-filter:blur(16px);border-radius:8px;box-shadow:0 18px 60px #0009;overflow:hidden}
    .left{left:16px}
    .right{right:16px;width:390px;display:flex;flex-direction:column}
    .head{height:42px;display:flex;align-items:center;justify-content:space-between;padding:0 12px;border-bottom:1px solid #263458;background:#0d1425}
    .body{padding:12px;overflow:auto}
    .row{display:flex;gap:8px;align-items:center;margin-bottom:8px}
    .grow{flex:1;min-width:0}
    .item{display:flex;align-items:center;justify-content:space-between;gap:8px;margin:7px 0;padding:8px 9px;border:1px solid #263756;background:#10172a;border-radius:7px}
    .item button{height:28px}
    .tag{display:inline-flex;align-items:center;height:24px;padding:0 8px;border-radius:999px;background:#17233d;border:1px solid #38496f;color:#cfe2ff;font-size:12px}
    .status{min-width:190px;color:#aebce1;font-size:12px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
    .editorTop{display:flex;gap:8px;margin-bottom:8px}
    .small{font-size:12px;color:#aebce1;word-break:break-all}
    .danger{background:#ff5b73;color:white;border-color:#ff8a9b}
    .mode{width:86px}
  `;
  document.head.appendChild(style);

  document.body.innerHTML = `
    <div id="cvmApp">
      <canvas id="space"></canvas>
      <div class="bar">
        <div class="brand">CVM Forge</div>
        <button class="pill hot" id="rootBtn">ROOT</button>
        <button class="pill" id="startBtn">START</button>
        <input class="grow" id="jump" placeholder="name / hash">
        <button class="pill" id="jumpBtn">跃迁</button>
        <input id="user" placeholder="user id" style="width:220px">
        <button class="pill ok" id="useUser">绑定</button>
        <div class="status" id="status">ready</div>
      </div>
      <section class="left">
        <div class="head"><b>块星图</b><span class="tag" id="count">0</span></div>
        <div class="body" id="roots"></div>
      </section>
      <section class="right">
        <div class="head"><b id="title">未选择</b><span class="tag" id="kind">node</span></div>
        <div class="body" id="info"></div>
        <div class="body" style="border-top:1px solid #263458">
          <div class="editorTop">
            <select id="mode" class="mode"><option value="js">JS</option><option value="block">BLOCK</option><option value="text">TEXT</option></select>
            <input class="grow" id="target" placeholder="target key hash">
          </div>
          <textarea id="editor" spellcheck="false"></textarea>
          <div class="row" style="margin-top:8px">
            <button class="pill hot" id="publish">发布</button>
            <button class="pill ok" id="personal">覆盖</button>
            <button class="pill" id="run">运行</button>
            <button class="pill danger" id="clear">清场</button>
          </div>
        </div>
      </section>
    </div>
  `;

  const $ = (s) => document.querySelector(s);
  const canvas = $("#space");
  const ctx = canvas.getContext("2d");
  const nodes = new Map();
  const edges = [];
  const incoming = new Map();
  const cache = new Map();

  let W = 0, H = 0, panX = 0, panY = 0, scale = 1;
  let selected = null, drag = null, panning = null;

  const status = (s) => $("#status").textContent = s;

  const resize = () => {
    W = canvas.width = innerWidth * devicePixelRatio;
    H = canvas.height = innerHeight * devicePixelRatio;
    ctx.setTransform(devicePixelRatio, 0, 0, devicePixelRatio, 0, 0);
  };
  addEventListener("resize", resize);
  resize();

  const nid = (type, h) => type + ":" + h;

  const addNode = (type, h, label) => {
    const id = nid(type, h);
    if (!nodes.has(id)) {
      nodes.set(id, {
        id, type, hash: h,
        label: label || nameByHash.get(h) || short(h),
        x: (Math.random() - .5) * 520,
        y: (Math.random() - .5) * 360,
        vx: 0, vy: 0,
        r: type === "key" ? 25 : 18,
        kind: type
      });
    }
    return nodes.get(id);
  };

  const addLink = (a, b, score = 0) => {
    if (!edges.some((e) => e.a === a && e.b === b)) edges.push({ a, b, score });
    if (b.startsWith("file:") && a.startsWith("key:")) incoming.set(b.slice(5), a.slice(4));
  };

  const parseBlock = (file) => {
    const out = [];
    for (let off = 0; off + 36 <= file.length;) {
      const n = read32At(file, off);
      out.push(hex(file.subarray(off + 4, off + 36)));
      off += 36 + n;
      if (n > file.length || off < 0) break;
    }
    return out;
  };

  const loadFile = async (fh) => {
    if (!cache.has(fh)) cache.set(fh, await download(unhex(fh)));
    return cache.get(fh);
  };

  const peekFile = async (fh) => {
    const file = await loadFile(fh);
    const f = addNode("file", fh);
    if (file[0] === 0) {
      f.kind = "block";
      f.label = "block " + short(fh);
      for (const kh of parseBlock(file)) {
        const k = addNode("key", kh);
        addLink(nid("file", fh), nid("key", kh));
      }
    } else {
      f.kind = "js";
      f.label = "js " + short(fh);
    }
  };

  const expandKey = async (kh, label) => {
    status("expand " + (label || short(kh)));
    const k = addNode("key", kh, label);
    const children = await childrenOf(kh);
    for (const c of children) {
      const f = addNode("file", c.hash);
      f.score = c.score;
      addLink(k.id, f.id, c.score);
      peekFile(c.hash).catch(() => {});
    }
    inspect(k);
    status("children " + children.length);
  };

  const makeBlock = async (text) => {
    const parts = text.split(/[\n,]+/).map((x) => x.trim()).filter(Boolean);
    const out = new Uint8Array(parts.length * 36);
    for (let i = 0; i < parts.length; i++) {
      const h = /^[0-9a-fA-F]{64}$/.test(parts[i]) ? unhex(parts[i]) : unhex(await keyOf(parts[i]));
      new DataView(out.buffer, i * 36, 4).setUint32(0, 0, true);
      out.set(h, i * 36 + 4);
    }
    return out;
  };

  const fileFromEditor = async () => {
    const mode = $("#mode").value;
    if (mode === "block") return makeBlock($("#editor").value);
    return enc.encode($("#editor").value);
  };

  const publishTo = async (personal) => {
    const target = $("#target").value.trim();
    if (!/^[0-9a-fA-F]{64}$/.test(target)) throw new Error("bad target");
    const file = await fileFromEditor();
    const fh = await upload(file);

    if (personal) {
      if (!cvm.USER) throw new Error("no user");
      await userSet(unhex(target), fh);
      cvm.HC.set(target, fh);
    } else {
      await addEdge(unhex(target), fh);
      if (cvm.USER) await vote(cvm.USER, unhex(target), fh).catch(() => {});
    }

    cvm.FC.set(hex(fh), file);
    cache.set(hex(fh), file);
    await expandKey(target);
    status((personal ? "override " : "publish ") + short(hex(fh)));
  };

  const inspect = async (n) => {
    selected = n;
    $("#title").textContent = n.label;
    $("#kind").textContent = n.kind || n.type;
    $("#count").textContent = String(nodes.size);

    if (n.type === "key") {
      $("#target").value = n.hash;
      $("#info").innerHTML = `
        <div class="small">${n.hash}</div>
        <div class="row" style="margin-top:10px">
          <button class="pill hot" id="expandOne">展开</button>
          <button class="pill" id="newBlock">新块</button>
          <button class="pill" id="newJS">新JS</button>
        </div>
      `;
      $("#expandOne").onclick = () => expandKey(n.hash, n.label);
      $("#newBlock").onclick = () => { $("#mode").value = "block"; $("#editor").value = "IF\nfor"; };
      $("#newJS").onclick = () => { $("#mode").value = "js"; $("#editor").value = "return CVM.resume();\n"; };
      return;
    }

    const file = await loadFile(n.hash);
    const target = incoming.get(n.hash);
    if (target) $("#target").value = target;

    if (file[0] === 0) {
      const keys = parseBlock(file);
      $("#mode").value = "block";
      $("#editor").value = keys.map((h) => nameByHash.get(h) || h).join("\n");
      $("#info").innerHTML = keys.map((h) => `
        <div class="item">
          <span>${nameByHash.get(h) || short(h)}</span>
          <button class="pill" data-key="${h}">展开</button>
        </div>
      `).join("") || `<div class="small">empty block</div>`;
      $("#info").querySelectorAll("[data-key]").forEach((b) => {
        b.onclick = () => expandKey(b.dataset.key, nameByHash.get(b.dataset.key));
      });
    } else {
      $("#mode").value = "js";
      $("#editor").value = bytesText(file);
      $("#info").innerHTML = `<div class="small">${n.hash}</div><div class="small">size ${file.length}</div>`;
    }
  };

  const roots = $("#roots");
  roots.innerHTML = names.map((n) => `<div class="item"><span>${n}</span><button class="pill" data-name="${n}">开</button></div>`).join("");
  roots.querySelectorAll("[data-name]").forEach((b) => {
    b.onclick = async () => expandKey(await keyOf(b.dataset.name), b.dataset.name);
  });

  $("#rootBtn").onclick = async () => expandKey(await keyOf("HTMLJSroot"), "HTMLJSroot");
  $("#startBtn").onclick = async () => expandKey(await keyOf("start"), "start");
  $("#jumpBtn").onclick = async () => {
    const v = $("#jump").value.trim();
    if (!v) return;
    const kh = /^[0-9a-fA-F]{64}$/.test(v) ? v : await keyOf(v);
    if (!/^[0-9a-fA-F]{64}$/.test(v)) nameByHash.set(kh, v);
    expandKey(kh, nameByHash.get(kh) || v);
  };
  $("#useUser").onclick = () => {
    const v = $("#user").value.trim();
    if (/^[0-9a-fA-F]{64}$/.test(v)) {
      cvm.user(v);
      status("user bound");
    }
  };
  $("#publish").onclick = () => publishTo(false).catch((e) => status(e.message));
  $("#personal").onclick = () => publishTo(true).catch((e) => status(e.message));
  $("#run").onclick = () => cvm.execute_call($("#editor").value).catch((e) => status(e.message));
  $("#clear").onclick = () => { nodes.clear(); edges.length = 0; incoming.clear(); };

  if (localStorage.cvmUser) {
    $("#user").value = localStorage.cvmUser;
    cvm.user(localStorage.cvmUser);
  }

  const world = (sx, sy) => ({
    x: (sx - innerWidth / 2 - panX) / scale,
    y: (sy - innerHeight / 2 - panY) / scale
  });

  const screen = (n) => ({
    x: innerWidth / 2 + panX + n.x * scale,
    y: innerHeight / 2 + panY + n.y * scale
  });

  const hit = (sx, sy) => {
    for (const n of [...nodes.values()].reverse()) {
      const p = screen(n);
      const r = n.r * scale + 8;
      if ((sx - p.x) ** 2 + (sy - p.y) ** 2 <= r * r) return n;
    }
    return null;
  };

  canvas.onmousedown = (e) => {
    const n = hit(e.clientX, e.clientY);
    if (n) {
      drag = n;
      n.fx = n.x;
      n.fy = n.y;
      inspect(n);
    } else {
      panning = { x: e.clientX, y: e.clientY, px: panX, py: panY };
    }
  };

  canvas.onmousemove = (e) => {
    if (drag) {
      const p = world(e.clientX, e.clientY);
      drag.x = p.x;
      drag.y = p.y;
      drag.vx = drag.vy = 0;
    }
    if (panning) {
      panX = panning.px + e.clientX - panning.x;
      panY = panning.py + e.clientY - panning.y;
    }
  };

  canvas.onmouseup = canvas.onmouseleave = () => { drag = null; panning = null; };
  canvas.ondblclick = (e) => {
    const n = hit(e.clientX, e.clientY);
    if (n?.type === "key") expandKey(n.hash, n.label);
  };
  canvas.onwheel = (e) => {
    e.preventDefault();
    scale = Math.max(.35, Math.min(2.4, scale * (e.deltaY > 0 ? .9 : 1.1)));
  };

  const physics = () => {
    const ns = [...nodes.values()];

    for (let i = 0; i < ns.length; i++) {
      for (let j = i + 1; j < ns.length; j++) {
        const a = ns[i], b = ns[j];
        let dx = b.x - a.x, dy = b.y - a.y;
        let d2 = dx * dx + dy * dy + .01;
        const f = Math.min(1800 / d2, 2.2);
        const d = Math.sqrt(d2);
        dx /= d; dy /= d;
        a.vx -= dx * f; a.vy -= dy * f;
        b.vx += dx * f; b.vy += dy * f;
      }
    }

    for (const e of edges) {
      const a = nodes.get(e.a), b = nodes.get(e.b);
      if (!a || !b) continue;
      const dx = b.x - a.x, dy = b.y - a.y;
      const d = Math.sqrt(dx * dx + dy * dy) || 1;
      const want = e.a.startsWith("key:") ? 125 : 95;
      const f = (d - want) * .012;
      a.vx += dx / d * f; a.vy += dy / d * f;
      b.vx -= dx / d * f; b.vy -= dy / d * f;
    }

    for (const n of ns) {
      if (n === drag) continue;
      n.vx *= .86; n.vy *= .86;
      n.x += n.vx; n.y += n.vy;
    }
  };

  const draw = () => {
    physics();
    ctx.clearRect(0, 0, innerWidth, innerHeight);

    ctx.save();
    ctx.globalAlpha = .25;
    ctx.strokeStyle = "#314064";
    for (let x = (panX % 40); x < innerWidth; x += 40) {
      ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, innerHeight); ctx.stroke();
    }
    for (let y = (panY % 40); y < innerHeight; y += 40) {
      ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(innerWidth, y); ctx.stroke();
    }
    ctx.restore();

    const t = performance.now() * .002;

    for (const e of edges) {
      const a = nodes.get(e.a), b = nodes.get(e.b);
      if (!a || !b) continue;
      const A = screen(a), B = screen(b);
      const g = ctx.createLinearGradient(A.x, A.y, B.x, B.y);
      g.addColorStop(0, "#62e6ff");
      g.addColorStop(1, "#ffcf5a");
      ctx.strokeStyle = g;
      ctx.globalAlpha = .45;
      ctx.lineWidth = Math.max(1, scale * 1.6);
      ctx.beginPath(); ctx.moveTo(A.x, A.y); ctx.lineTo(B.x, B.y); ctx.stroke();

      const p = (Math.sin(t + e.score) + 1) / 2;
      ctx.globalAlpha = .9;
      ctx.fillStyle = "#ffffff";
      ctx.beginPath();
      ctx.arc(A.x + (B.x - A.x) * p, A.y + (B.y - A.y) * p, 2.5, 0, Math.PI * 2);
      ctx.fill();
    }

    ctx.globalAlpha = 1;
    for (const n of nodes.values()) {
      const p = screen(n);
      const r = n.r * scale;
      const key = n.type === "key";
      ctx.shadowBlur = selected === n ? 28 : 16;
      ctx.shadowColor = key ? "#54e7ff" : n.kind === "block" ? "#ffcf5a" : "#ff5bd7";
      ctx.fillStyle = key ? "#57e6ff" : n.kind === "block" ? "#ffd45e" : "#ff67dc";
      ctx.beginPath();
      ctx.arc(p.x, p.y, r, 0, Math.PI * 2);
      ctx.fill();
      ctx.shadowBlur = 0;
      ctx.fillStyle = "#07101b";
      ctx.beginPath();
      ctx.arc(p.x, p.y, r * .52, 0, Math.PI * 2);
      ctx.fill();

      ctx.fillStyle = "#f7fbff";
      ctx.font = "12px ui-sans-serif, system-ui";
      ctx.textAlign = "center";
      ctx.fillText(n.label, p.x, p.y + r + 15);
    }

    requestAnimationFrame(draw);
  };

  draw();
  expandKey(await keyOf("HTMLJSroot"), "HTMLJSroot").catch((e) => status(e.message));
})();
'''

CONTINUE_JS = "CVM.PTR.off = 0;\nreturn CVM.executeBlock();\n"


def sha(s: bytes) -> bytes:
    return hashlib.sha256(s).digest()


def key(name: str) -> bytes:
    return sha(name.encode())


def block(names) -> bytes:
    return b"".join(struct.pack("<I", 0) + key(name) for name in names)


def read_id(path: str) -> str:
    raw = Path(path).read_bytes()
    if len(raw) == 32:
        return raw.hex()
    text = raw.strip()
    if re.fullmatch(rb"[0-9a-fA-F]{64}", text):
        return text.decode().lower()
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
            raise RuntimeError(f"{method} {path} HTTP {e.code}: {body.decode(errors='replace')}")
        obj = json.loads(body.decode())
        if not obj.get("ok"):
            raise RuntimeError(f"{method} {path}: {obj}")
        return obj

    def upload(self, data: bytes):
        return self.call("POST", "/api/upload", data)["data"]["hash"]

    def edge(self, parent: str, child: str):
        return self.call("POST", f"/api/edge/{parent}/{child}")

    def vote(self, user: str, parent: str, child: str):
        return self.call("POST", f"/api/vote/{user}/{parent}/{child}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default=BASE_DEFAULT)
    ap.add_argument("--id", default="id.bin")
    args = ap.parse_args()

    api = API(args.base)
    user = read_id(args.id)

    files = [
        ("start", "start.js", START_JS.encode()),
        ("continue", "continue.js", CONTINUE_JS.encode()),
        ("HTMLJSstart", "start.bin", block(["start", "continue"])),
        ("HTMLJSroot", "root.bin", block(ROOT_CHILDREN)),
        ("Process control", "process_control.bin", block(PROCESS_CHILDREN)),
    ]

    print("base:", args.base)
    print("user:", user)
    print()

    for parent_name, file_name, data in files:
        parent = key(parent_name).hex()
        local_hash = sha(data).hex()

        uploaded = api.upload(data)
        edge_result = api.edge(parent, uploaded)
        vote_result = api.vote(user, parent, uploaded)

        print(f"{parent_name} -> {file_name}")
        print("  key        :", parent)
        print("  file hash  :", uploaded)
        print("  local hash :", local_hash)
        print("  upload     :", uploaded == local_hash)
        print("  edge       :", edge_result)
        print("  vote       :", vote_result)
        print()

    print("root 浏览结构：")
    print("HTMLJSroot")
    for x in ROOT_CHILDREN:
        print(" ", x)
    print("Process control")
    for x in PROCESS_CHILDREN:
        print(" ", x)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print("ERROR:", e, file=sys.stderr)
        sys.exit(1)