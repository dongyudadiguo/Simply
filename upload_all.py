#!/usr/bin/env python3
import hashlib
import json
import os
import re
import struct
import urllib.error
import urllib.request

API_BASE = "http://124.221.146.23:9000"
ID_BIN = os.path.join(os.path.dirname(__file__), "id.bin")


BOOT_JS = r'''
CVM.apiBase = "__API_BASE__";

// 如果还没有用户 ID，显示手动选择按钮（避免浏览器拦截自动文件对话框）
async function ensureUserId() {
  if (localStorage.getItem("CVM.user")) return;

  document.body.innerHTML = `
    <div style="min-height:100vh;background:#020617;color:#e5e7eb;font-family:system-ui,sans-serif;padding:30px;box-sizing:border-box">
      <h2>请选择 id.bin</h2>
      <p>第一次需要选择一次 id.bin，之后会自动记住。</p>
      <input id="idbin" type="file" accept=".bin,.txt,*">
      <pre id="idout" style="margin-top:16px;padding:12px;background:#0f172a;border:1px solid #334155;white-space:pre-wrap">waiting...</pre>
    </div>
  `;

  await new Promise(resolve => {
    const input = document.querySelector("#idbin");
    const out = document.querySelector("#idout");

    input.onchange = async () => {
      const file = input.files[0];
      if (!file) return;

      try {
        const raw = new Uint8Array(await file.arrayBuffer());
        let id = "";

        if (raw.length === 32) {
          id = [...raw].map(b => b.toString(16).padStart(2, "0")).join("");
        } else {
          const text = new TextDecoder().decode(raw);
          const m = /[0-9a-fA-F]{64}/.exec(text);
          if (m) id = m[0].toLowerCase();
        }

        if (!/^[0-9a-f]{64}$/.test(id)) {
          out.textContent = "bad id.bin";
          return;
        }

        localStorage.setItem("CVM.user", id);
        out.textContent = "ok\n" + id;
        resolve();
      } catch (e) {
        out.textContent = String(e);
      }
    };
  });
}

await ensureUserId();

CVM.readInt = p => {
  const v = new DataView(p.buf.buffer, p.buf.byteOffset + p.off, 4).getUint32(0, true);
  p.off += 4;
  return v;
};

CVM.downloadHex = async hex => {
  const r = await fetch(`${CVM.apiBase}/api/file/${hex}`);
  if (!r.ok) throw new Error(`download failed: ${hex}`);
  return new Uint8Array(await r.arrayBuffer());
};

CVM.resolveHex = async (ptrHex, user) => {
  if (user) {
    const u = await fetch(`${CVM.apiBase}/api/user/get/${user}/${ptrHex}`)
      .then(r => r.json()).catch(() => null);
    if (u?.ok && u.data?.value) return u.data.value;
  }

  const c = await fetch(`${CVM.apiBase}/api/children/${ptrHex}`)
    .then(r => r.json()).catch(() => null);

  return c?.data?.children?.[0]?.hash || ptrHex;
};

CVM.skipCurrentCall = ctx => {
  ctx.ptr.off += 36;
  let n;
  while ((n = CVM.readInt(ctx.ptr))) ctx.ptr.off += 32 + n;
};

CVM.continueExecution = async function continueExecution(ctx = CVM.ctx) {
  CVM.skipCurrentCall(ctx);

  while (true) {
    if (ctx.ptr.off + 36 > ctx.ptr.buf.length) {
      if (ctx.stack.length) {
        ctx.ptr = ctx.stack.pop();
        continue;
      }
      ctx.ptr.off = 0;
      return;
    }

    ctx.ptr.off += 4;

    const ptrHex = CVM.hex(ctx.ptr.buf.subarray(ctx.ptr.off, ctx.ptr.off += 32));
    const targetHex = await CVM.resolveHex(ptrHex, ctx.user);

    const file = ctx.cache[targetHex] || (ctx.cache[targetHex] = await CVM.downloadHex(targetHex));
    const fileHex = CVM.hex(await CVM.sha256(file));

    if (ctx.user && fileHex !== targetHex) {
      fetch(`${CVM.apiBase}/api/user/set/${ctx.user}/${ptrHex}/${fileHex}`, { method: "POST" }).catch(() => {});
    }

    if (file[0] !== 0) {
      await CVM.execute_call(new TextDecoder().decode(file));
      break;
    }

    ctx.stack.push({ buf: ctx.ptr.buf, off: ctx.ptr.off });
    ctx.ptr = { buf: file, off: 0 };
  }
};

CVM.showError = err => {
  console.error(err);
  document.body.innerHTML = `<pre style="white-space:pre-wrap;margin:0;padding:16px;background:#450a0a;color:#fecaca;min-height:100vh">${String(err?.stack || err)}</pre>`;
};

const knownNames = ["HTMLJSroot", "HTMLJSstart", "game", "blockend"];
CVM.nameMap = {};
for (const name of knownNames) CVM.nameMap[CVM.hex(await CVM.sha256(name))] = name;

const esc = s => String(s).replace(/[&<>"']/g, c => ({
  "&": "&amp;",
  "<": "&lt;",
  ">": "&gt;",
  '"': "&quot;",
  "'": "&#39;",
}[c]));

async function fileText(hex, max = 4000) {
  try {
    const b = await CVM.downloadHex(hex);
    const s = new TextDecoder().decode(b);
    const bad = [...s.slice(0, 200)].filter(ch => ch < " " && !"\n\r\t".includes(ch)).length;
    if (bad > 10) return "";
    return s.trim().slice(0, max);
  } catch {
    return "";
  }
}

async function titleOf(hex) {
  const real = await CVM.resolveHex(hex, CVM.ctx?.user || "");
  const txt = await fileText(real, 120);
  if (txt) return txt.split("\n")[0].slice(0, 80);
  if (CVM.nameMap[hex]) return CVM.nameMap[hex];
  return `${hex.slice(0, 8)}...${hex.slice(-8)}`;
}

async function showBlock(hex) {
  const real = await CVM.resolveHex(hex, CVM.ctx?.user || "");
  const txt = await fileText(real);

  document.querySelector("#main").innerHTML = `
    <div class="title">${esc(await titleOf(hex))}</div>
    <pre>${esc(txt || "(没有可显示的文本内容)")}</pre>
    <div id="stage"></div>
  `;
}

const nav = [];

async function enterBlock(hex, push = false) {
  if (push && CVM.currentHex) nav.push(CVM.currentHex);
  CVM.currentHex = hex;

  const tree = document.querySelector("#tree-body");
  tree.innerHTML = "";

  const home = document.createElement("div");
  home.className = "node";
  home.textContent = "🏠 HTMLJSroot";
  home.onclick = () => {
    nav.length = 0;
    enterBlock(CVM.rootHex);
  };
  tree.appendChild(home);

  if (nav.length) {
    const back = document.createElement("div");
    back.className = "node";
    back.textContent = "← 返回";
    back.onclick = () => enterBlock(nav.pop());
    tree.appendChild(back);
  }

  const title = document.createElement("div");
  title.className = "title";
  title.textContent = await titleOf(hex);
  tree.appendChild(title);

  await showBlock(hex);

  const j = await fetch(`${CVM.apiBase}/api/children/${hex}`).then(r => r.json()).catch(() => null);
  const kids = j?.data?.children || [];

  if (!kids.length) {
    const empty = document.createElement("div");
    empty.style.color = "#64748b";
    empty.textContent = "没有子块";
    tree.appendChild(empty);
    return;
  }

  for (const kid of kids) {
    const row = document.createElement("div");
    row.className = "node";
    row.textContent = await titleOf(kid.hash);
    row.title = kid.hash;
    row.onclick = () => enterBlock(kid.hash, true);
    tree.appendChild(row);
  }
}

document.body.innerHTML = `
<style>
body {
  margin: 0;
  background: #0f172a;
  color: #e5e7eb;
  font-family: system-ui, sans-serif;
}
#app {
  display: grid;
  grid-template-columns: 340px 1fr;
  height: 100vh;
}
#tree {
  background: #020617;
  border-right: 1px solid #334155;
  padding: 14px;
  overflow: auto;
}
#main {
  padding: 18px;
  overflow: auto;
}
.title {
  color: #93c5fd;
  font-weight: 700;
  margin: 12px 0 8px;
}
.node {
  padding: 6px 8px;
  margin: 2px 0;
  border-radius: 8px;
  cursor: pointer;
  word-break: break-all;
}
.node:hover {
  background: #1e293b;
}
pre {
  white-space: pre-wrap;
  background: #020617;
  border: 1px solid #334155;
  border-radius: 8px;
  padding: 12px;
}
button {
  background: #2563eb;
  color: white;
  border: 0;
  border-radius: 8px;
  padding: 8px 12px;
  margin-right: 8px;
  cursor: pointer;
}
canvas {
  background: #020617;
  border: 1px solid #334155;
  border-radius: 8px;
}
</style>

<div id="app">
  <aside id="tree">
    <div class="title">联网块浏览器</div>
    <div id="tree-body"></div>
  </aside>
  <main id="main">
    <div id="stage"></div>
  </main>
</div>
`;

try {
  CVM.ctx = {
    user: localStorage.getItem("CVM.user") || "",
    ptr: CVM.PTR,
    stack: [],
    cache: {},
  };

  CVM.rootHex = CVM.hex(await CVM.sha256("HTMLJSroot"));

  await enterBlock(CVM.rootHex);
  await CVM.continueExecution(CVM.ctx);
} catch (err) {
  CVM.showError(err);
}
'''


GAME_JS = r'''
const stage = document.querySelector("#stage");

stage.innerHTML = `
  <div class="title">小游戏：吃金币</div>
  <canvas id="cv" width="480" height="320"></canvas>
  <div style="margin-top:12px">
    <button id="finish">结束本轮 / blockend</button>
    <button id="reset">重开</button>
    <span style="margin-left:12px">分数：<b id="score">0</b></span>
  </div>
  <p style="color:#94a3b8">方向键或 WASD 移动蓝色方块，吃掉黄色金币。</p>
`;

const canvas = document.querySelector("#cv");
const g = canvas.getContext("2d");
const scoreEl = document.querySelector("#score");

const W = 15;
const H = 10;
const S = 32;

let score = 0;
let player = { x: 1, y: 1 };
let coin = { x: 8, y: 5 };

function placeCoin() {
  do {
    coin.x = Math.floor(Math.random() * W);
    coin.y = Math.floor(Math.random() * H);
  } while (coin.x === player.x && coin.y === player.y);
}

function draw() {
  g.clearRect(0, 0, canvas.width, canvas.height);
  g.fillStyle = "#020617";
  g.fillRect(0, 0, canvas.width, canvas.height);

  g.strokeStyle = "#1e293b";
  for (let x = 0; x <= W; x++) {
    g.beginPath();
    g.moveTo(x * S, 0);
    g.lineTo(x * S, H * S);
    g.stroke();
  }
  for (let y = 0; y <= H; y++) {
    g.beginPath();
    g.moveTo(0, y * S);
    g.lineTo(W * S, y * S);
    g.stroke();
  }

  g.fillStyle = "#facc15";
  g.beginPath();
  g.arc(coin.x * S + S / 2, coin.y * S + S / 2, 10, 0, Math.PI * 2);
  g.fill();

  g.fillStyle = "#60a5fa";
  g.fillRect(player.x * S + 4, player.y * S + 4, S - 8, S - 8);

  scoreEl.textContent = String(score);
}

function move(dx, dy) {
  player.x = Math.max(0, Math.min(W - 1, player.x + dx));
  player.y = Math.max(0, Math.min(H - 1, player.y + dy));

  if (player.x === coin.x && player.y === coin.y) {
    score++;
    placeCoin();
  }

  draw();
}

if (CVM.gameKeyHandler) {
  window.removeEventListener("keydown", CVM.gameKeyHandler);
}

CVM.gameKeyHandler = e => {
  const k = e.key.toLowerCase();
  if (e.key === "ArrowUp" || k === "w") move(0, -1);
  if (e.key === "ArrowDown" || k === "s") move(0, 1);
  if (e.key === "ArrowLeft" || k === "a") move(-1, 0);
  if (e.key === "ArrowRight" || k === "d") move(1, 0);
};

window.addEventListener("keydown", CVM.gameKeyHandler);

document.querySelector("#reset").onclick = () => {
  score = 0;
  player = { x: 1, y: 1 };
  placeCoin();
  draw();
};

document.querySelector("#finish").onclick = async () => {
  try {
    if (CVM.ctx.stack.length) {
      CVM.ctx.ptr = CVM.ctx.stack.pop();
    }
    await CVM.continueExecution(CVM.ctx);
  } catch (err) {
    CVM.showError(err);
  }
};

placeCoin();
draw();
'''


BLOCKEND_JS = r'''
const ctx = CVM.ctx;

if (!ctx) throw new Error("blockend: missing CVM.ctx");

if (ctx.stack.length) {
  ctx.ptr = ctx.stack.pop();
  await CVM.continueExecution(ctx);
} else {
  ctx.ptr.off = 0;
}
'''


def sha_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def key_hex(name: str) -> str:
    return sha_hex(name.encode("utf-8"))


def load_user_id(path: str) -> str:
    raw = open(path, "rb").read().strip()

    if len(raw) == 32:
        return raw.hex()

    text = raw.decode("utf-8", "ignore").strip()
    m = re.search(r"[0-9a-fA-F]{64}", text)
    if m:
        return m.group(0).lower()

    raise RuntimeError(f"bad id.bin: {path}")


def u32(n: int) -> bytes:
    return struct.pack("<I", n)


def vm_call(ptr_hex: str) -> bytes:
    return b"\x00" * 4 + bytes.fromhex(ptr_hex) + b"\x00" * 36 + u32(0)


def make_start_block(boot_hash: str, game_key: str, blockend_key: str) -> bytes:
    return (
        bytes.fromhex(boot_hash)
        + b"\x00" * 4
        + u32(0)
        + vm_call(game_key)
        + vm_call(blockend_key)
    )


class API:
    def __init__(self, base: str):
        self.base = base.rstrip("/")

    def req(self, method: str, path: str, body=None, headers=None):
        headers = dict(headers or {})

        if isinstance(body, (dict, list)):
            body = json.dumps(body).encode("utf-8")
            headers["Content-Type"] = "application/json"

        req = urllib.request.Request(
            self.base + path,
            data=body,
            method=method,
            headers=headers,
        )

        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                raw = resp.read()
        except urllib.error.HTTPError as e:
            msg = e.read().decode("utf-8", "replace")
            raise RuntimeError(f"{method} {path} HTTP {e.code}: {msg}")

        return json.loads(raw.decode("utf-8")) if raw else None

    def upload(self, data: bytes, name: str) -> str:
        h = sha_hex(data)
        j = self.req(
            "POST",
            "/api/upload",
            body=data,
            headers={"Content-Type": "application/octet-stream"},
        )
        got = j["data"]["hash"]
        if got != h:
            raise RuntimeError(f"hash mismatch {name}: {got} != {h}")
        print(f"[upload] {name}: {got}")
        return got

    def edge(self, parent: str, child: str, name: str = ""):
        j = self.req("POST", f"/api/edge/{parent}/{child}", body=b"")
        if not j or not j.get("ok"):
            raise RuntimeError(f"edge failed: {parent} -> {child}")
        print(f"[edge] {name}")

    def vote(self, user: str, parent: str, child: str):
        j = self.req("POST", f"/api/vote/{user}/{parent}/{child}", body=b"")
        if not j or not j.get("ok"):
            raise RuntimeError(f"vote failed: {parent} -> {child}")

    def user_set(self, user: str, key: str, value: str):
        j = self.req("POST", f"/api/user/set/{user}/{key}/{value}", body=b"")
        if not j or not j.get("ok"):
            raise RuntimeError(f"user_set failed: {key} -> {value}")


def main():
    api = API(API_BASE)

    root_key = key_hex("HTMLJSroot")
    start_key = key_hex("HTMLJSstart")
    game_key = key_hex("game")
    blockend_key = key_hex("blockend")

    game_hash = api.upload(GAME_JS.encode("utf-8"), "game.js")
    blockend_hash = api.upload(BLOCKEND_JS.encode("utf-8"), "blockend.js")
    boot_hash = api.upload(BOOT_JS.replace("__API_BASE__", API_BASE).encode("utf-8"), "boot.js")

    start_hash = api.upload(
        make_start_block(boot_hash, game_key, blockend_key),
        "HTMLJSstart.block",
    )

    edges = [
        (root_key, start_key, "HTMLJSroot -> HTMLJSstart"),
        (start_key, start_hash, "HTMLJSstart -> start block"),
        (start_hash, game_key, "start block -> game"),
        (start_hash, blockend_key, "start block -> blockend"),
        (game_key, game_hash, "game -> game.js"),
        (blockend_key, blockend_hash, "blockend -> blockend.js"),
    ]

    for parent, child, name in edges:
        api.edge(parent, child, name)

    user = load_user_id(ID_BIN)
    print(f"[user] {user}")

    api.user_set(user, root_key, start_key)
    api.user_set(user, start_key, start_hash)
    api.user_set(user, game_key, game_hash)
    api.user_set(user, blockend_key, blockend_hash)

    for parent, child, _ in edges:
        api.vote(user, parent, child)

    print()
    print("done")
    print("HTMLJSroot  =", root_key)
    print("HTMLJSstart =", start_key)
    print("start block =", start_hash)
    print("boot js     =", boot_hash)
    print("game js     =", game_hash)
    print("blockend js =", blockend_hash)


if __name__ == "__main__":
    main()