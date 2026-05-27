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
/*
  CVM Studio
  - runtime self editor
  - graphical block/file browser
  - Monaco code editor with textarea fallback
*/

const cvm = globalThis.CVM;
const enc = new TextEncoder();
const dec = new TextDecoder();

const hex = (x) =>
  typeof x === "string" ? x.toLowerCase() : cvm.hex(x);

const unhex = (h) =>
  new Uint8Array((h.match(/../g) || []).map((x) => parseInt(x, 16)));

const esc = (s) =>
  String(s).replace(/[&<>"']/g, (c) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
  }[c]));

const short = (h, n = 8) =>
  h ? `${h.slice(0, n)}…${h.slice(-n)}` : "";

const isHex64 = (s) =>
  /^[0-9a-fA-F]{64}$/.test(String(s || "").trim());

const zeroHash = new Uint8Array(32);

const isZeroHash = (b) => {
  if (!b || b.length < 32) return false;
  for (let i = 0; i < 32; i++) {
    if (b[i] !== 0) return false;
  }
  return true;
};

const readU32 = (buf, off) =>
  new DataView(buf.buffer, buf.byteOffset + off, 4).getUint32(0, true);

const writeU32Hash = (n) => {
  const b = new Uint8Array(32);
  new DataView(b.buffer).setUint32(0, n, true);
  return b;
};

const isSizeHashAt = (buf, off) => {
  if (off + 32 > buf.length) return false;

  for (let i = off + 4; i < off + 32; i++) {
    if (buf[i] !== 0) return false;
  }

  return readU32(buf, off) !== 0;
};

const concatBytes = (xs) => {
  const n = xs.reduce((s, x) => s + x.length, 0);
  const out = new Uint8Array(n);
  let off = 0;

  for (const x of xs) {
    out.set(x, off);
    off += x.length;
  }

  return out;
};

const bytesToPrettyHex = (b) => {
  let out = "";

  for (let i = 0; i < b.length; i++) {
    out += b[i].toString(16).padStart(2, "0");
    out += (i + 1) % 16 === 0 ? "\n" : " ";
  }

  return out.trim();
};

const parseLooseHex = (s) => {
  const clean = String(s).replace(/[^0-9a-fA-F]/g, "");

  if (clean.length % 2) {
    throw new Error("hex 长度必须是偶数");
  }

  return unhex(clean);
};

const hashName = async (name) =>
  hex(await cvm.sha256(name));

/* ---------------------------------------------------------
   Install / upgrade standard continuation helpers.
   This keeps the normal CVM API usable inside the studio.
--------------------------------------------------------- */

(() => {
  const download = async (fileHash) => {
    const k = hex(fileHash);

    cvm.FC ??= new Map();

    if (!cvm.FC.has(k)) {
      cvm.FC.set(k, await cvm.download_file(fileHash));
    }

    return cvm.FC.get(k);
  };

  const upload = async (file) =>
    unhex((await (await fetch(`${apiBase}/api/upload`, {
      method: "POST",
      body: file,
    })).json()).data.hash);

  const userGet = async (keyHash) =>
    unhex((await (await fetch(
      `${apiBase}/api/user/get/${hex(cvm.USER)}/${hex(keyHash)}`
    )).json()).data.value);

  const userSet = async (keyHash, fileHash) =>
    fetch(`${apiBase}/api/user/set/${hex(cvm.USER)}/${hex(keyHash)}/${hex(fileHash)}`, {
      method: "POST",
    });

  cvm.FC ??= new Map();
  cvm.HC ??= new Map();
  cvm.OV ??= new Map();
  cvm.ST ??= [];

  cvm.gethashhashfile = async (keyHash) => {
    const k = hex(keyHash);

    if (cvm.OV.has(k)) {
      return cvm.OV.get(k);
    }

    if (!cvm.HC.has(k)) {
      let fileHash;

      if (cvm.USER) {
        try {
          fileHash = await userGet(keyHash);
        } catch {
          fileHash = await cvm.getfirstchild(keyHash);
        }
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

      if (cvm.USER) {
        await userSet(unhex(keyHex), fileHash);
      }

      cvm.HC.set(keyHex, fileHash);
      cvm.FC.set(hex(fileHash), file);
    }

    cvm.OV.clear();
  };

  cvm.override = (keyHash, file) => {
    cvm.OV.set(hex(keyHash), file);
  };

  cvm.user = (userId) => {
    cvm.USER = hex(userId);
    cvm.HC.clear();
  };

  cvm.executeBlock = async () => {
    for (;;) {
      const keyHash = cvm.PTR.buf.subarray(cvm.PTR.off, cvm.PTR.off + 32);

      if (isZeroHash(keyHash)) {
        if (!cvm.ST.length) return;

        cvm.PTR = cvm.ST.pop();
        return cvm.resume();
      }

      const file = await cvm.gethashhashfile(keyHash);

      if (file[0]) {
        return cvm.execute_call(dec.decode(file));
      }

      await cvm.Modify_override();

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
    cvm.PTR.off += 32;

    while (isSizeHashAt(cvm.PTR.buf, cvm.PTR.off)) {
      const n = readU32(cvm.PTR.buf, cvm.PTR.off);
      cvm.PTR.off += 32 + n;
    }

    return cvm.executeBlock();
  };
})();

/* ---------------------------------------------------------
   DOM shell
--------------------------------------------------------- */

document.getElementById("cvmStudio")?.remove();
document.getElementById("cvmStudioStyle")?.remove();

const style = document.createElement("style");
style.id = "cvmStudioStyle";
style.textContent = `
  html, body {
    margin: 0;
    width: 100%;
    min-height: 100%;
    overflow: hidden;
    background: #05020d;
  }

  #cvmStudio {
    position: fixed;
    inset: 0;
    z-index: 2147483000;
    color: #f8f7ff;
    font-family: ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    background:
      radial-gradient(circle at 10% 10%, rgba(255,0,180,.28), transparent 32%),
      radial-gradient(circle at 82% 18%, rgba(0,220,255,.24), transparent 30%),
      radial-gradient(circle at 50% 90%, rgba(116,255,99,.18), transparent 35%),
      linear-gradient(135deg, #09031a, #05020d 58%, #02040b);
    overflow: hidden;
  }

  #cvmStudio::before {
    content: "";
    position: absolute;
    inset: 0;
    pointer-events: none;
    background-image:
      linear-gradient(rgba(255,255,255,.035) 1px, transparent 1px),
      linear-gradient(90deg, rgba(255,255,255,.035) 1px, transparent 1px);
    background-size: 38px 38px;
    mask-image: radial-gradient(circle at center, black, transparent 85%);
  }

  .cvmTop {
    position: absolute;
    left: 18px;
    right: 18px;
    top: 14px;
    height: 58px;
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 0 14px;
    border: 1px solid rgba(255,255,255,.14);
    border-radius: 20px;
    background: rgba(10, 8, 26, .72);
    backdrop-filter: blur(18px);
    box-shadow: 0 0 36px rgba(0,220,255,.12), inset 0 0 24px rgba(255,255,255,.04);
  }

  .logo {
    font-weight: 900;
    letter-spacing: .08em;
    font-size: 18px;
    text-shadow: 0 0 18px #00e5ff;
    white-space: nowrap;
  }

  .chip {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    height: 30px;
    padding: 0 10px;
    border-radius: 999px;
    color: #dffbff;
    border: 1px solid rgba(0,230,255,.28);
    background: rgba(0,230,255,.08);
    font-size: 12px;
    white-space: nowrap;
  }

  .topInput {
    height: 32px;
    min-width: 260px;
    flex: 1;
    color: #fff;
    padding: 0 10px;
    outline: none;
    border-radius: 12px;
    border: 1px solid rgba(255,255,255,.16);
    background: rgba(255,255,255,.06);
    font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  }

  button {
    color: #fff;
    cursor: pointer;
    border: 0;
    border-radius: 12px;
    padding: 8px 11px;
    background: linear-gradient(135deg, rgba(255,0,160,.9), rgba(0,210,255,.9));
    box-shadow: 0 0 18px rgba(0,220,255,.18);
    font-weight: 700;
  }

  button:hover {
    filter: brightness(1.16);
    transform: translateY(-1px);
  }

  button.ghost {
    border: 1px solid rgba(255,255,255,.16);
    background: rgba(255,255,255,.08);
    box-shadow: none;
  }

  button.danger {
    background: linear-gradient(135deg, #ff3860, #ff9c00);
  }

  label.check {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    font-size: 12px;
    opacity: .92;
    white-space: nowrap;
  }

  #cvmStage {
    position: absolute;
    inset: 86px 18px 72px 18px;
    border-radius: 26px;
    border: 1px solid rgba(255,255,255,.1);
    background: rgba(255,255,255,.035);
    overflow: hidden;
    box-shadow: inset 0 0 80px rgba(0,0,0,.3);
  }

  #cvmLinks {
    position: absolute;
    inset: 0;
    width: 100%;
    height: 100%;
    overflow: visible;
    pointer-events: none;
  }

  #cvmNodes {
    position: absolute;
    inset: 0;
  }

  .node {
    position: absolute;
    width: 340px;
    max-height: 620px;
    overflow: hidden;
    border-radius: 22px;
    border: 1px solid rgba(255,255,255,.16);
    background: linear-gradient(180deg, rgba(18,18,42,.92), rgba(10,8,24,.85));
    box-shadow: 0 18px 50px rgba(0,0,0,.36), 0 0 30px rgba(0,220,255,.12);
    backdrop-filter: blur(16px);
  }

  .node.block {
    border-color: rgba(0,240,255,.26);
  }

  .node.code {
    border-color: rgba(255,0,190,.28);
  }

  .nodeHead {
    padding: 13px 14px;
    cursor: grab;
    user-select: none;
    background: linear-gradient(90deg, rgba(255,255,255,.10), rgba(255,255,255,.02));
    border-bottom: 1px solid rgba(255,255,255,.1);
  }

  .nodeTitle {
    font-size: 15px;
    font-weight: 900;
    line-height: 1.25;
  }

  .meta {
    margin-top: 7px;
    display: flex;
    flex-wrap: wrap;
    gap: 5px;
  }

  code, .mono {
    font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  }

  .pill {
    display: inline-block;
    max-width: 300px;
    overflow: hidden;
    text-overflow: ellipsis;
    padding: 3px 7px;
    border-radius: 999px;
    font-size: 11px;
    color: #d7fbff;
    border: 1px solid rgba(255,255,255,.12);
    background: rgba(255,255,255,.06);
  }

  .nodeBody {
    padding: 12px;
    overflow: auto;
    max-height: 510px;
  }

  .tools {
    display: flex;
    flex-wrap: wrap;
    gap: 7px;
    margin-bottom: 10px;
  }

  .slot {
    margin: 8px 0;
    padding: 9px;
    border-radius: 16px;
    border: 1px solid rgba(255,255,255,.12);
    background: rgba(255,255,255,.055);
  }

  .slot.ref {
    box-shadow: inset 3px 0 0 rgba(0,230,255,.8);
  }

  .slot.data {
    box-shadow: inset 3px 0 0 rgba(140,255,100,.8);
  }

  .slotTop {
    display: flex;
    justify-content: space-between;
    gap: 8px;
    align-items: center;
    font-size: 12px;
  }

  .slotBtns {
    display: flex;
    gap: 5px;
    flex-wrap: wrap;
    margin-top: 8px;
  }

  .slotBtns button {
    padding: 5px 8px;
    font-size: 11px;
  }

  .preview {
    margin: 8px 0 0;
    max-height: 260px;
    overflow: auto;
    padding: 10px;
    white-space: pre-wrap;
    border-radius: 14px;
    color: #dff;
    background: rgba(0,0,0,.33);
    border: 1px solid rgba(255,255,255,.08);
    font-size: 12px;
  }

  #cvmLog {
    position: absolute;
    left: 18px;
    right: 18px;
    bottom: 14px;
    height: 44px;
    display: flex;
    align-items: center;
    gap: 10px;
    overflow: hidden;
    padding: 0 14px;
    border-radius: 18px;
    color: #d9fcff;
    background: rgba(5, 5, 18, .72);
    border: 1px solid rgba(255,255,255,.1);
    backdrop-filter: blur(14px);
    font-size: 12px;
  }

  .logMsg {
    white-space: nowrap;
    opacity: .95;
  }

  .modalMask {
    position: fixed;
    inset: 0;
    z-index: 2147483100;
    background: rgba(0,0,0,.62);
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .modal {
    width: min(1180px, calc(100vw - 60px));
    height: min(760px, calc(100vh - 70px));
    display: flex;
    flex-direction: column;
    overflow: hidden;
    border-radius: 24px;
    border: 1px solid rgba(255,255,255,.18);
    background: linear-gradient(180deg, rgba(18,18,42,.98), rgba(6,5,18,.98));
    box-shadow: 0 0 80px rgba(0,220,255,.25);
  }

  .modalHead {
    height: 54px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0 14px;
    border-bottom: 1px solid rgba(255,255,255,.12);
  }

  .modalTitle {
    font-weight: 900;
  }

  .modalBody {
    flex: 1;
    min-height: 0;
    padding: 12px;
  }

  .modalFoot {
    display: flex;
    justify-content: flex-end;
    gap: 8px;
    padding: 12px;
    border-top: 1px solid rgba(255,255,255,.12);
  }

  textarea.big {
    width: 100%;
    height: 100%;
    resize: none;
    box-sizing: border-box;
    color: #eaffff;
    background: rgba(0,0,0,.45);
    border: 1px solid rgba(255,255,255,.12);
    border-radius: 16px;
    padding: 12px;
    outline: none;
    font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  }

  .split {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 12px;
    height: 100%;
  }

  .miniTitle {
    margin-bottom: 7px;
    font-size: 12px;
    opacity: .76;
  }

  .dirty {
    color: #ffdf6e;
    text-shadow: 0 0 10px rgba(255,220,80,.5);
  }

  .okText {
    color: #7dffb2;
  }

  .badText {
    color: #ff809a;
  }
`;
document.head.appendChild(style);

const app = document.createElement("div");
app.id = "cvmStudio";
app.innerHTML = `
  <div class="cvmTop">
    <div class="logo">🧬 CVM STUDIO</div>
    <span class="chip">runtime self-editor</span>
    <input id="cvmUserInput" class="topInput" placeholder="user id，64 hex；启动代码公开发布需要它投票">
    <button id="cvmUseUser" class="ghost">使用ID</button>
    <button id="cvmRegister" class="ghost">注册</button>
    <label class="check">
      <input id="cvmPublish" type="checkbox" checked>
      公开发布+投票
    </label>
    <button id="cvmOpenRoot">启动块</button>
    <button id="cvmOpenStart">自身代码</button>
  </div>

  <div id="cvmStage">
    <svg id="cvmLinks"></svg>
    <div id="cvmNodes"></div>
  </div>

  <div id="cvmLog">
    <span class="chip">log</span>
    <div id="cvmLogText" class="logMsg">ready</div>
  </div>

  <div id="cvmModalRoot"></div>
`;
document.body.appendChild(app);

const nodesEl = document.getElementById("cvmNodes");
const linksEl = document.getElementById("cvmLinks");
const stageEl = document.getElementById("cvmStage");
const modalRoot = document.getElementById("cvmModalRoot");
const logText = document.getElementById("cvmLogText");
const userInput = document.getElementById("cvmUserInput");
const publishInput = document.getElementById("cvmPublish");

const rootKeyHex = await hashName("HTMLJSstart");
const startKeyHex = hex(cvm.PTR.buf.subarray(0, 32));

const state = {
  user: localStorage.getItem("cvm.user") || "",
  nextNodeId: 1,
  nodes: new Map(),
  links: [],
};

if (state.user) {
  userInput.value = state.user;
  cvm.user(state.user);
}

const log = (msg, bad = false) => {
  logText.innerHTML = `<span class="${bad ? "badText" : "okText"}">${esc(new Date().toLocaleTimeString())}</span> ${esc(msg)}`;
};

/* ---------------------------------------------------------
   Server API
--------------------------------------------------------- */

const apiJson = async (path, opt = {}) => {
  const res = await fetch(`${apiBase}${path}`, opt);
  const text = await res.text();

  let json;
  try {
    json = JSON.parse(text);
  } catch {
    throw new Error(`${path}: bad json: ${text.slice(0, 200)}`);
  }

  if (!res.ok || !json.ok) {
    throw new Error(json.error || `${path}: HTTP ${res.status}`);
  }

  return json.data;
};

const downloadByFileHash = async (fileHashHex) => {
  cvm.FC ??= new Map();

  if (cvm.FC.has(fileHashHex)) {
    return cvm.FC.get(fileHashHex);
  }

  const res = await fetch(`${apiBase}/api/file/${fileHashHex}`);

  if (!res.ok) {
    throw new Error(`download failed: ${fileHashHex}`);
  }

  const file = new Uint8Array(await res.arrayBuffer());
  cvm.FC.set(fileHashHex, file);
  return file;
};

const firstChildHex = async (keyHex) => {
  const data = await apiJson(`/api/children/${keyHex}`);

  if (!data.children || !data.children.length) {
    throw new Error(`no child: ${keyHex}`);
  }

  return data.children[0].hash;
};

const userGetHex = async (keyHex) => {
  if (!state.user) throw new Error("no user");

  const data = await apiJson(`/api/user/get/${state.user}/${keyHex}`);
  return data.value;
};

const uploadFile = async (bytes) => {
  const data = await apiJson("/api/upload", {
    method: "POST",
    body: bytes,
  });

  return data.hash;
};

const resolveKey = async (keyHex) => {
  cvm.HC ??= new Map();
  cvm.OV ??= new Map();

  if (cvm.OV.has(keyHex)) {
    return {
      fileHashHex: "local override",
      file: cvm.OV.get(keyHex),
    };
  }

  let fileHashHex;

  if (state.user) {
    try {
      fileHashHex = await userGetHex(keyHex);
    } catch {
      fileHashHex = await firstChildHex(keyHex);
    }
  } else {
    fileHashHex = await firstChildHex(keyHex);
  }

  const file = await downloadByFileHash(fileHashHex);
  cvm.HC.set(keyHex, unhex(fileHashHex));

  return {
    fileHashHex,
    file,
  };
};

const saveKey = async (keyHex, bytes) => {
  const publish = publishInput.checked;
  const fileHashHex = await uploadFile(bytes);

  cvm.FC ??= new Map();
  cvm.HC ??= new Map();

  cvm.FC.set(fileHashHex, bytes);
  cvm.HC.set(keyHex, unhex(fileHashHex));
  cvm.OV?.delete(keyHex);

  if (state.user) {
    await apiJson(`/api/user/set/${state.user}/${keyHex}/${fileHashHex}`, {
      method: "POST",
    });
  }

  if (publish) {
    await apiJson(`/api/edge/${keyHex}/${fileHashHex}`, {
      method: "POST",
    });

    if (state.user) {
      await apiJson(`/api/vote/${state.user}/${keyHex}/${fileHashHex}`, {
        method: "POST",
      });
    } else {
      log("已加公共边，但没有 user id，无法投票；可能不会成为 firstchild", true);
    }
  }

  if (!state.user && !publish) {
    log("只上传了文件，没有绑定到 key；刷新后不会生效", true);
  }

  return fileHashHex;
};

/* ---------------------------------------------------------
   Block parse / build
--------------------------------------------------------- */

const parseBlock = (buf) => {
  const items = [];
  let off = 0;
  let ended = false;

  while (off + 32 <= buf.length) {
    const slot = buf.subarray(off, off + 32);

    if (isZeroHash(slot)) {
      ended = true;
      break;
    }

    if (isSizeHashAt(buf, off)) {
      const size = readU32(buf, off);
      const dataStart = off + 32;
      const dataEnd = Math.min(dataStart + size, buf.length);

      items.push({
        type: "data",
        off,
        size,
        data: buf.slice(dataStart, dataEnd),
      });

      off = dataStart + size;
      continue;
    }

    items.push({
      type: "ref",
      off,
      keyHex: hex(slot),
    });

    off += 32;
  }

  return {
    items,
    ended,
    endOff: off,
  };
};

const buildBlock = (items) => {
  const xs = [];

  for (const it of items) {
    if (it.type === "ref") {
      xs.push(unhex(it.keyHex));
    } else {
      xs.push(writeU32Hash(it.data.length));
      xs.push(it.data);
    }
  }

  xs.push(zeroHash);
  return concatBytes(xs);
};

/* ---------------------------------------------------------
   Graph UI
--------------------------------------------------------- */

const placeNear = (parentId) => {
  const parent = state.nodes.get(parentId);

  if (!parent) {
    return {
      x: 40 + Math.random() * 80,
      y: 90 + Math.random() * 80,
    };
  }

  const k = state.links.filter((x) => x.from === parentId).length;

  return {
    x: parent.x + 390,
    y: parent.y + k * 135 - 30,
  };
};

const addLink = (from, to) => {
  if (!from || !to || from === to) return;

  if (!state.links.some((x) => x.from === from && x.to === to)) {
    state.links.push({ from, to });
  }
};

const findNodeByKey = (keyHex) =>
  [...state.nodes.values()].find((n) => n.keyHex === keyHex);

const openRoot = () => {
  if (state.nodes.has("root")) {
    render();
    return;
  }

  const node = {
    id: "root",
    type: "block",
    title: "🌍 HTMLJSstart 启动块 / start.bin",
    keyHex: rootKeyHex,
    fileHashHex: "boot-memory",
    buf: new Uint8Array(cvm.PTR.buf),
    x: 36,
    y: 44,
    dirty: false,
  };

  node.items = parseBlock(node.buf).items;
  state.nodes.set(node.id, node);
  render();
};

const openKey = async (keyOrHex, parentId = null, title = "") => {
  const keyHex = hex(keyOrHex);
  const existed = findNodeByKey(keyHex);

  if (existed) {
    addLink(parentId, existed.id);
    render();
    return existed;
  }

  log(`resolving ${short(keyHex)} ...`);

  const resolved = await resolveKey(keyHex);
  const pos = placeNear(parentId);
  const isBlock = resolved.file[0] === 0;

  const node = {
    id: `n${state.nextNodeId++}`,
    type: isBlock ? "block" : "code",
    title: title || (isBlock ? `🧩 block ${short(keyHex)}` : `⚡ code ${short(keyHex)}`),
    keyHex,
    fileHashHex: resolved.fileHashHex,
    buf: new Uint8Array(resolved.file),
    x: pos.x,
    y: pos.y,
    dirty: false,
  };

  if (isBlock) {
    node.items = parseBlock(node.buf).items;
  }

  state.nodes.set(node.id, node);
  addLink(parentId, node.id);

  log(`${isBlock ? "opened block" : "opened code"} ${short(keyHex)}`);
  render();
  return node;
};

const markDirty = (node) => {
  node.dirty = true;

  if (node.type === "block") {
    node.buf = buildBlock(node.items);
  }

  render();
};

const saveNode = async (node) => {
  if (node.type === "block") {
    node.buf = buildBlock(node.items);
  }

  log(`saving ${node.title} ...`);

  const fileHashHex = await saveKey(node.keyHex, node.buf);

  node.fileHashHex = fileHashHex;
  node.dirty = false;

  if (node.id === "root") {
    cvm.PTR.buf = node.buf;
  }

  log(`saved ${node.title} -> ${short(fileHashHex)}`);
  render();
};

const attachDrag = (card, node) => {
  const head = card.querySelector(".nodeHead");

  head.onpointerdown = (ev) => {
    ev.preventDefault();

    const sx = ev.clientX;
    const sy = ev.clientY;
    const ox = node.x;
    const oy = node.y;

    head.setPointerCapture(ev.pointerId);

    head.onpointermove = (e) => {
      node.x = ox + e.clientX - sx;
      node.y = oy + e.clientY - sy;

      card.style.left = `${node.x}px`;
      card.style.top = `${node.y}px`;

      drawLinks();
    };

    head.onpointerup = () => {
      head.onpointermove = null;
      head.onpointerup = null;
    };
  };
};

const nodeMeta = (node) => `
  <div class="meta">
    <span class="pill">key ${short(node.keyHex, 10)}</span>
    <span class="pill">file ${short(node.fileHashHex, 10)}</span>
    <span class="pill">${node.buf.length} bytes</span>
    ${node.dirty ? `<span class="pill dirty">unsaved</span>` : ""}
  </div>
`;

const renderBlockNode = (node) => {
  const card = document.createElement("div");
  card.id = `node-${node.id}`;
  card.className = "node block";
  card.style.left = `${node.x}px`;
  card.style.top = `${node.y}px`;

  const slots = node.items.map((it, i) => {
    if (it.type === "ref") {
      return `
        <div class="slot ref">
          <div class="slotTop">
            <b>🔗 #${i} ref</b>
            <code>${short(it.keyHex, 12)}</code>
          </div>
          <div class="slotBtns">
            <button data-open="${i}">打开</button>
            <button class="ghost" data-edit-ref="${i}">改hash</button>
            <button class="ghost" data-up="${i}">↑</button>
            <button class="ghost" data-down="${i}">↓</button>
            <button class="danger" data-del="${i}">删</button>
          </div>
        </div>
      `;
    }

    return `
      <div class="slot data">
        <div class="slotTop">
          <b>💾 #${i} data</b>
          <span>${it.data.length} bytes</span>
        </div>
        <div class="slotBtns">
          <button data-bin="${i}">bin-editor</button>
          <button class="ghost" data-up="${i}">↑</button>
          <button class="ghost" data-down="${i}">↓</button>
          <button class="danger" data-del="${i}">删</button>
        </div>
      </div>
    `;
  }).join("");

  card.innerHTML = `
    <div class="nodeHead">
      <div class="nodeTitle">${esc(node.title)}</div>
      ${nodeMeta(node)}
    </div>
    <div class="nodeBody">
      <div class="tools">
        <button data-save>保存块</button>
        <button class="ghost" data-add-ref>+ ref</button>
        <button class="ghost" data-add-data>+ data</button>
        <button class="ghost" data-reparse>重解析</button>
      </div>
      ${slots || `<div class="slot">空块。末尾保存时会自动追加全零 hash。</div>`}
    </div>
  `;

  nodesEl.appendChild(card);
  attachDrag(card, node);

  card.querySelector("[data-save]").onclick = () => saveNode(node).catch((e) => log(e.message, true));

  card.querySelector("[data-reparse]").onclick = () => {
    node.items = parseBlock(node.buf).items;
    node.dirty = false;
    render();
  };

  card.querySelector("[data-add-ref]").onclick = async () => {
    const s = prompt("输入 64 位 hex key；或者输入名字，会自动 sha256(name)：");

    if (s == null) return;

    const keyHex = isHex64(s) ? s.trim().toLowerCase() : await hashName(s);
    node.items.push({ type: "ref", keyHex });
    markDirty(node);
  };

  card.querySelector("[data-add-data]").onclick = () => {
    showBinEditor("新增 data 段", new Uint8Array(), (bytes) => {
      node.items.push({
        type: "data",
        data: bytes,
      });

      markDirty(node);
    });
  };

  card.querySelectorAll("[data-open]").forEach((btn) => {
    btn.onclick = () => {
      const i = Number(btn.dataset.open);
      openKey(node.items[i].keyHex, node.id).catch((e) => log(e.message, true));
    };
  });

  card.querySelectorAll("[data-bin]").forEach((btn) => {
    btn.onclick = () => {
      const i = Number(btn.dataset.bin);

      showBinEditor(`编辑 data #${i}`, node.items[i].data, (bytes) => {
        node.items[i].data = bytes;
        markDirty(node);
      });
    };
  });

  card.querySelectorAll("[data-edit-ref]").forEach((btn) => {
    btn.onclick = async () => {
      const i = Number(btn.dataset.editRef);
      const old = node.items[i].keyHex;
      const s = prompt("输入 64 位 hex key；或者输入名字，会自动 sha256(name)：", old);

      if (s == null) return;

      node.items[i].keyHex = isHex64(s) ? s.trim().toLowerCase() : await hashName(s);
      markDirty(node);
    };
  });

  card.querySelectorAll("[data-del]").forEach((btn) => {
    btn.onclick = () => {
      const i = Number(btn.dataset.del);
      node.items.splice(i, 1);
      markDirty(node);
    };
  });

  card.querySelectorAll("[data-up]").forEach((btn) => {
    btn.onclick = () => {
      const i = Number(btn.dataset.up);

      if (i <= 0) return;

      [node.items[i - 1], node.items[i]] = [node.items[i], node.items[i - 1]];
      markDirty(node);
    };
  });

  card.querySelectorAll("[data-down]").forEach((btn) => {
    btn.onclick = () => {
      const i = Number(btn.dataset.down);

      if (i >= node.items.length - 1) return;

      [node.items[i + 1], node.items[i]] = [node.items[i], node.items[i + 1]];
      markDirty(node);
    };
  });
};

const renderCodeNode = (node) => {
  const src = dec.decode(node.buf);
  const card = document.createElement("div");
  card.id = `node-${node.id}`;
  card.className = "node code";
  card.style.left = `${node.x}px`;
  card.style.top = `${node.y}px`;

  card.innerHTML = `
    <div class="nodeHead">
      <div class="nodeTitle">${esc(node.title)}</div>
      ${nodeMeta(node)}
    </div>
    <div class="nodeBody">
      <div class="tools">
        <button data-edit>Monaco 编辑</button>
        <button class="ghost" data-run>热运行</button>
        <button class="ghost" data-save>保存源码</button>
      </div>
      <pre class="preview">${esc(src.slice(0, 1600))}${src.length > 1600 ? "\n\n/* ... */" : ""}</pre>
    </div>
  `;

  nodesEl.appendChild(card);
  attachDrag(card, node);

  card.querySelector("[data-edit]").onclick = () => {
    showCodeEditor(node).catch((e) => log(e.message, true));
  };

  card.querySelector("[data-run]").onclick = async () => {
    try {
      log(`running ${node.title} ...`);
      await cvm.execute_call(dec.decode(node.buf));
      log(`finished ${node.title}`);
    } catch (e) {
      log(e.message || String(e), true);
      console.error(e);
    }
  };

  card.querySelector("[data-save]").onclick = () => saveNode(node).catch((e) => log(e.message, true));
};

const render = () => {
  nodesEl.innerHTML = "";

  for (const node of state.nodes.values()) {
    if (node.type === "block") {
      renderBlockNode(node);
    } else {
      renderCodeNode(node);
    }
  }

  setTimeout(drawLinks, 20);
};

const drawLinks = () => {
  const srect = stageEl.getBoundingClientRect();
  const paths = [];

  for (const l of state.links) {
    const a = document.getElementById(`node-${l.from}`);
    const b = document.getElementById(`node-${l.to}`);

    if (!a || !b) continue;

    const ar = a.getBoundingClientRect();
    const br = b.getBoundingClientRect();

    const x1 = ar.right - srect.left;
    const y1 = ar.top + ar.height / 2 - srect.top;
    const x2 = br.left - srect.left;
    const y2 = br.top + br.height / 2 - srect.top;

    const mx = Math.max(80, Math.abs(x2 - x1) * 0.45);

    paths.push(`
      <path d="M ${x1} ${y1} C ${x1 + mx} ${y1}, ${x2 - mx} ${y2}, ${x2} ${y2}"
        fill="none"
        stroke="rgba(0,235,255,.62)"
        stroke-width="3"
        filter="drop-shadow(0 0 8px rgba(0,235,255,.9))" />
    `);
  }

  linksEl.innerHTML = paths.join("");
};

/* ---------------------------------------------------------
   Modals
--------------------------------------------------------- */

const showModal = (title) => {
  const mask = document.createElement("div");
  mask.className = "modalMask";
  mask.innerHTML = `
    <div class="modal">
      <div class="modalHead">
        <div class="modalTitle">${esc(title)}</div>
        <button class="ghost" data-close>关闭</button>
      </div>
      <div class="modalBody"></div>
      <div class="modalFoot"></div>
    </div>
  `;

  modalRoot.appendChild(mask);

  const close = () => mask.remove();

  mask.querySelector("[data-close]").onclick = close;

  return {
    mask,
    body: mask.querySelector(".modalBody"),
    foot: mask.querySelector(".modalFoot"),
    close,
  };
};

const showBinEditor = (title, initialBytes, onSave) => {
  const m = showModal(title);

  m.body.innerHTML = `
    <div class="split">
      <div>
        <div class="miniTitle">HEX</div>
        <textarea class="big" id="binHex"></textarea>
      </div>
      <div>
        <div class="miniTitle">TEXT preview / input</div>
        <textarea class="big" id="binText"></textarea>
      </div>
    </div>
  `;

  m.foot.innerHTML = `
    <button class="ghost" data-text-to-hex>文字转hex</button>
    <button class="ghost" data-hex-to-text>hex转文字</button>
    <button data-save>应用</button>
  `;

  const hexTa = m.body.querySelector("#binHex");
  const textTa = m.body.querySelector("#binText");

  hexTa.value = bytesToPrettyHex(initialBytes);

  try {
    textTa.value = dec.decode(initialBytes);
  } catch {
    textTa.value = "";
  }

  m.foot.querySelector("[data-text-to-hex]").onclick = () => {
    hexTa.value = bytesToPrettyHex(enc.encode(textTa.value));
  };

  m.foot.querySelector("[data-hex-to-text]").onclick = () => {
    try {
      textTa.value = dec.decode(parseLooseHex(hexTa.value));
    } catch (e) {
      log(e.message, true);
    }
  };

  m.foot.querySelector("[data-save]").onclick = () => {
    try {
      const bytes = parseLooseHex(hexTa.value);
      onSave(bytes);
      m.close();
    } catch (e) {
      log(e.message, true);
    }
  };
};

let monacoPromise = null;

const ensureMonaco = () => {
  if (globalThis.monaco) return Promise.resolve(globalThis.monaco);
  if (monacoPromise) return monacoPromise;

  monacoPromise = new Promise((resolve, reject) => {
    const loader = document.createElement("script");
    loader.src = "https://cdnjs.cloudflare.com/ajax/libs/monaco-editor/0.45.0/min/vs/loader.min.js";

    loader.onload = () => {
      try {
        globalThis.require.config({
          paths: {
            vs: "https://cdnjs.cloudflare.com/ajax/libs/monaco-editor/0.45.0/min/vs",
          },
        });

        globalThis.require(["vs/editor/editor.main"], () => {
          resolve(globalThis.monaco);
        }, reject);
      } catch (e) {
        reject(e);
      }
    };

    loader.onerror = reject;
    document.head.appendChild(loader);
  });

  return monacoPromise;
};

const showCodeEditor = async (node) => {
  const m = showModal(`编辑源码：${node.title}`);

  m.body.innerHTML = `<div id="editorMount" style="height:100%; border-radius:16px; overflow:hidden;"></div>`;
  m.foot.innerHTML = `
    <button class="ghost" data-apply>暂存到节点</button>
    <button data-save>保存</button>
    <button data-save-run>保存+热运行</button>
  `;

  const mount = m.body.querySelector("#editorMount");
  const initial = dec.decode(node.buf);

  let getValue;
  let dispose = () => {};

  try {
    const monaco = await ensureMonaco();

    const editor = monaco.editor.create(mount, {
      value: initial,
      language: "javascript",
      theme: "vs-dark",
      automaticLayout: true,
      minimap: {
        enabled: false,
      },
      fontSize: 14,
      wordWrap: "on",
    });

    getValue = () => editor.getValue();
    dispose = () => editor.dispose();
  } catch {
    mount.innerHTML = `<textarea class="big"></textarea>`;
    const ta = mount.querySelector("textarea");
    ta.value = initial;
    getValue = () => ta.value;
  }

  const apply = () => {
    node.buf = enc.encode(getValue());
    node.dirty = true;
    render();
  };

  m.foot.querySelector("[data-apply]").onclick = () => {
    apply();
    log("已暂存到图节点，还没有写入服务器");
  };

  m.foot.querySelector("[data-save]").onclick = async () => {
    try {
      apply();
      await saveNode(node);
      dispose();
      m.close();
    } catch (e) {
      log(e.message, true);
    }
  };

  m.foot.querySelector("[data-save-run]").onclick = async () => {
    try {
      apply();
      await saveNode(node);
      await cvm.execute_call(dec.decode(node.buf));
      dispose();
      m.close();
    } catch (e) {
      log(e.message, true);
      console.error(e);
    }
  };
};

/* ---------------------------------------------------------
   Top controls
--------------------------------------------------------- */

const setUser = (id) => {
  id = String(id || "").trim().toLowerCase();

  if (!isHex64(id)) {
    throw new Error("user id 必须是 64 位 hex");
  }

  state.user = id;
  localStorage.setItem("cvm.user", id);
  userInput.value = id;
  cvm.user(id);
  log(`user = ${short(id, 12)}`);
};

document.getElementById("cvmUseUser").onclick = () => {
  try {
    setUser(userInput.value);
  } catch (e) {
    log(e.message, true);
  }
};

document.getElementById("cvmRegister").onclick = async () => {
  try {
    const token = prompt("Turnstile token；如果服务器没有开启 Turnstile，可以留空：") || "";
    const data = await apiJson("/api/register", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ token }),
    });

    setUser(data.id);
  } catch (e) {
    log(e.message, true);
  }
};

document.getElementById("cvmOpenRoot").onclick = openRoot;

document.getElementById("cvmOpenStart").onclick = () => {
  openKey(startKeyHex, "root", "🚀 start.js / 正在运行的自身代码")
    .catch((e) => log(e.message, true));
};

/* ---------------------------------------------------------
   Boot studio
--------------------------------------------------------- */

openRoot();

await openKey(
  startKeyHex,
  "root",
  "🚀 start.js / 正在运行的自身代码"
).catch((e) => log(e.message, true));

log("拖拽节点，点击 ref 打开网络块；保存启动代码请使用公开发布+投票");
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