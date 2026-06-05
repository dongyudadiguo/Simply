#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import hashlib
import json
import re
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

BASE_DEFAULT = "http://124.221.146.23:9000"
ZERO_HASH = b"\x00" * 32
ZERO_HEX = "00" * 32


def sha(data: bytes) -> bytes:
    return hashlib.sha256(data).digest()


def key(name: str) -> bytes:
    return sha(name.encode())


def le32(n: int) -> bytes:
    return int(n).to_bytes(4, "little")


def block(items) -> bytes:
    out = bytearray()

    for item in items:
        if isinstance(item, str):
            name = item
            data = b""
        else:
            name, data = item
            if isinstance(data, str):
                data = data.encode()
            data = data or b""

        name_hash = key(name) if isinstance(name, str) else bytes.fromhex(name)

        out += name_hash
        out += len(data).to_bytes(4, "little")
        out += data

    out += ZERO_HASH
    return bytes(out)


class API:
    def __init__(self, base: str):
        self.base = base.rstrip("/")

    def request(self, method: str, path: str, data=None, headers=None) -> bytes:
        req = urllib.request.Request(
            self.base + path,
            data=data,
            method=method,
            headers=headers or {},
        )
        return urllib.request.urlopen(req).read()

    def json(self, method: str, path: str, data=None, headers=None):
        raw = self.request(method, path, data, headers)
        out = json.loads(raw.decode())

        if not out.get("ok"):
            raise RuntimeError(out.get("error", "api error"))

        return out.get("data")

    def upload(self, data: bytes) -> str:
        return self.json("POST", "/api/upload", data)["hash"]

    def edge(self, parent: str, child: str):
        self.json("POST", f"/api/edge/{parent}/{child}", b"")

    def vote(self, user: str, parent: str, child: str):
        self.json("POST", f"/api/vote/{user}/{parent}/{child}", b"")

    def children(self, parent: str):
        try:
            return self.json("GET", f"/api/children/{parent}")["children"]
        except Exception:
            return []

    def file(self, file_hash: str):
        try:
            return self.request("GET", f"/api/file/{file_hash}")
        except urllib.error.HTTPError as err:
            if err.code == 404:
                return None
            raise

    def register(self) -> str:
        data = json.dumps({"token": ""}).encode()
        return self.json(
            "POST",
            "/api/register",
            data,
            {"Content-Type": "application/json"},
        )["id"]


def get_or_create_id(api: API, path: str) -> str:
    p = Path(path)

    if p.exists():
        raw = p.read_bytes()

        if len(raw) == 32:
            return raw.hex()

        m = re.search(rb"[0-9a-fA-F]{64}", raw)
        if m:
            return m.group(0).decode().lower()

    print("id.bin 不存在，正在注册新用户...")
    user = api.register()
    p.write_bytes(bytes.fromhex(user))
    print(f"已注册并保存新用户: {user}")
    return user


def ensure_direct_file(api: API, data: bytes) -> str:
    file_hash = sha(data).hex()
    old = api.file(file_hash)

    if old == data:
        return file_hash

    got = api.upload(data)
    if got != file_hash:
        raise RuntimeError("upload hash mismatch")

    return got


def first_child(api: API, parent: str):
    xs = api.children(parent)
    return xs[0]["hash"] if xs else None


def put_if_changed(api: API, user: str, name: str, data: bytes):
    parent = key(name).hex()
    child = sha(data).hex()

    # 让 key(name) 本身可下载成名字文本，用于浏览器显示 tag。
    ensure_direct_file(api, name.encode())

    current = first_child(api, parent)

    if current == child:
        print(f"[=] {name} unchanged")
        return child

    ensure_direct_file(api, data)
    api.edge(parent, child)
    api.vote(user, parent, child)

    if current:
        print(f"[*] {name} updated -> {child[:16]}...")
    else:
        print(f"[+] {name} created -> {child[:16]}...")

    return child


def mount_root(api: API, user: str, name: str):
    child = key(name).hex()
    existing = {x["hash"] for x in api.children(ZERO_HEX)}

    if child in existing:
        print(f"[=] root/{name} mounted")
        return

    api.edge(ZERO_HEX, child)
    api.vote(user, ZERO_HEX, child)
    print(f"[+] root/{name} mounted")


def no_data_meter(label: str) -> str:
    html = f"""
      <div style="padding:7px 2px;color:#8c8580;font-weight:900">
        {label}<br>
        <span style="font-weight:700;font-size:11px">此节点没有节点参数 data。</span>
      </div>
    """
    return "async ({ body }) => { body.innerHTML = " + json.dumps(html) + "; }"


def svg_for(name: str) -> str:
    text = name[:4]
    return f"""<svg viewBox="0 0 64 64" xmlns="http://www.w3.org/2000/svg">
  <rect x="8" y="8" width="48" height="48" rx="8" fill="#fffaf1" stroke="#2a211c" stroke-width="4"/>
  <text x="32" y="40" font-size="18" fill="#2a211c" text-anchor="middle" font-family="monospace" font-weight="900">{text}</text>
</svg>"""


def make_index_html(base: str) -> str:
    base = base.rstrip("/")
    return f"""<!doctype html>
<meta charset="utf-8">
<title>CVM</title>
<script>
const apiBase = globalThis.apiBase = {json.dumps(base)};

const textEncoder = new TextEncoder();
const textDecoder = new TextDecoder();

const CVM = globalThis.CVM = {{
  PTR: null,
  IMP: null,
}};

const toBytes = (value) =>
  value instanceof Uint8Array ? value :
  value instanceof ArrayBuffer ? new Uint8Array(value) :
  ArrayBuffer.isView(value) ? new Uint8Array(value.buffer, value.byteOffset, value.byteLength) :
  textEncoder.encode(String(value));

const toHex = (value) =>
  [...toBytes(value)].map((byte) => byte.toString(16).padStart(2, "0")).join("");

const fromHex = (hex) =>
  new Uint8Array((String(hex).match(/../g) || []).map((x) => parseInt(x, 16)));

const sha256 = async (value) =>
  new Uint8Array(await crypto.subtle.digest("SHA-256", toBytes(value)));

const downloadFile = async (hash) =>
  new Uint8Array(await (await fetch(`${{apiBase}}/api/file/${{toHex(hash)}}`)).arrayBuffer());

const getfirstchild = async (parent) => {{
  const res = await fetch(`${{apiBase}}/api/children/${{toHex(parent)}}`);
  const json = await res.json();

  if (!json.ok || !json.data.children.length) {{
    throw new Error("no child");
  }}

  return fromHex(json.data.children[0].hash);
}};

Object.assign(CVM, {{
  sha256,
  str_sha: sha256,
  hex: toHex,
  download_file: downloadFile,
  getfirstchild,
  execute_call: (source) => eval(`(async()=>{{${{source}}}})()`),
}});

(async () => {{
  const startFileData = await downloadFile(await getfirstchild(await sha256("HTMLJSstart")));

  CVM.PTR = {{
    buf: startFileData,
    off: 0,
  }};

  const javaScriptHash = startFileData.subarray(0, 32);
  const javaScriptSource = textDecoder.decode(await downloadFile(await getfirstchild(javaScriptHash)));

  CVM.IMP = () => eval(`(async()=>{{${{javaScriptSource}}}})()`);
  await CVM.IMP();
}})();
</script>
"""


LOADER_JS = r"""
{
  const cvm = CVM;
  const dec = new TextDecoder();
  const enc = new TextEncoder();

  const bytes = (x) =>
    x instanceof Uint8Array ? x :
    x instanceof ArrayBuffer ? new Uint8Array(x) :
    ArrayBuffer.isView(x) ? new Uint8Array(x.buffer, x.byteOffset, x.byteLength) :
    enc.encode(String(x ?? ""));

  const toHex = (x) =>
    [...bytes(x)].map((b) => b.toString(16).padStart(2, "0")).join("");

  const hex = (x) =>
    typeof x === "string" ? x.trim().toLowerCase() : toHex(x);

  const unhex = (h) => {
    h = String(h || "").trim();
    if (!h) return new Uint8Array();
    const m = h.match(/../g) || [];
    return new Uint8Array(m.map((x) => parseInt(x, 16)));
  };

  const u32 = (b, o) =>
    new DataView(b.buffer, b.byteOffset, b.byteLength).getUint32(o, true);

  const zhash = (b, o) => {
    if (o + 32 > b.length) return false;
    for (let i = o; i < o + 32; i++) if (b[i]) return false;
    return true;
  };

  const isBlockFile = (file) => {
    file = bytes(file);
    let o = 0;

    for (;;) {
      if (o + 32 > file.length) return false;
      if (zhash(file, o)) return o + 32 === file.length;
      if (o + 36 > file.length) return false;

      const n = u32(file, o + 32);
      if (n > file.length - o - 36) return false;

      o += 36 + n;
    }
  };

  const dlen = () =>
    zhash(cvm.PTR.buf, cvm.PTR.off) ? 0 : u32(cvm.PTR.buf, cvm.PTR.off + 32);

  const readHash = () =>
    cvm.PTR.buf.subarray(cvm.PTR.off, cvm.PTR.off + 32);

  cvm.bytes ??= bytes;
  cvm.hex ??= hex;
  cvm.unhex ??= unhex;
  cvm.u32 ??= u32;
  cvm.zhash ??= zhash;
  cvm.isBlockFile ??= isBlockFile;
  cvm.FC ??= new Map();
  cvm.HC ??= new Map();
  cvm.ST ??= [];

  const downloadCached = async (h) => {
    const k = hex(h);
    if (!cvm.FC.has(k)) cvm.FC.set(k, await cvm.download_file(h));
    return cvm.FC.get(k);
  };

  cvm.gethashhashfile ??= async (keyHash) => {
    const k = hex(keyHash);

    if (!cvm.HC.has(k)) {
      cvm.HC.set(k, await cvm.getfirstchild(keyHash));
    }

    return downloadCached(cvm.HC.get(k));
  };

  cvm.resume = async () => {
    cvm.PTR.off += 36 + dlen();
    return cvm.executeBlock();
  };

  cvm.executeBlock = async () => {
    for (;;) {
      if (cvm.Modify_override) await cvm.Modify_override();

      if (zhash(cvm.PTR.buf, cvm.PTR.off)) {
        const prev = cvm.ST.pop();

        if (!prev) return;

        cvm.PTR = prev;
        return cvm.resume();
      }

      const file = await cvm.gethashhashfile(readHash());

      if (isBlockFile(file)) {
        cvm.ST.push({
          buf: cvm.PTR.buf,
          off: cvm.PTR.off,
        });

        cvm.PTR = {
          buf: file,
          off: 0,
        };

        continue;
      }

      return cvm.execute_call(dec.decode(file));
    }
  };

  return cvm.resume();
}
"""


CORE_CODEC_JS = r"""
{
  const cvm = CVM;

  cvm.textEncoder ??= new TextEncoder();
  cvm.textDecoder ??= new TextDecoder();

  cvm.bytes = (x) =>
    x instanceof Uint8Array ? x :
    x instanceof ArrayBuffer ? new Uint8Array(x) :
    ArrayBuffer.isView(x) ? new Uint8Array(x.buffer, x.byteOffset, x.byteLength) :
    cvm.textEncoder.encode(String(x ?? ""));

  cvm.toHex = (x) =>
    [...cvm.bytes(x)].map((b) => b.toString(16).padStart(2, "0")).join("");

  cvm.hex = (x) =>
    typeof x === "string" ? x.trim().toLowerCase() : cvm.toHex(x);

  cvm.unhex = (h) => {
    h = String(h || "").trim().replace(/[^0-9a-f]/gi, "");
    if (!h) return new Uint8Array();
    if (h.length % 2) h = h.slice(0, -1);
    return new Uint8Array((h.match(/../g) || []).map((x) => parseInt(x, 16)));
  };

  cvm.concat = (...xs) => {
    xs = xs.map(cvm.bytes);

    const out = new Uint8Array(xs.reduce((n, x) => n + x.length, 0));
    let o = 0;

    for (const x of xs) {
      out.set(x, o);
      o += x.length;
    }

    return out;
  };

  cvm.u32 = (b, o = 0) =>
    new DataView(b.buffer, b.byteOffset, b.byteLength).getUint32(o, true);

  cvm.writeU32 = (b, o, n) =>
    new DataView(b.buffer, b.byteOffset, b.byteLength).setUint32(o, n >>> 0, true);

  cvm.u32bytes = (n) => {
    const b = new Uint8Array(4);
    cvm.writeU32(b, 0, n);
    return b;
  };

  cvm.sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

  return cvm.resume();
}
"""


CORE_BLOCK_JS = r"""
{
  const cvm = CVM;

  cvm.ZERO_HASH ??= new Uint8Array(32);

  cvm.zhash = (b, o = 0) => {
    if (o + 32 > b.length) return false;
    for (let i = o; i < o + 32; i++) if (b[i]) return false;
    return true;
  };

  cvm.isBlockFile = (file) => {
    file = cvm.bytes(file);
    let o = 0;

    for (;;) {
      if (o + 32 > file.length) return false;
      if (cvm.zhash(file, o)) return o + 32 === file.length;
      if (o + 36 > file.length) return false;

      const n = cvm.u32(file, o + 32);
      if (n > file.length - o - 36) return false;

      o += 36 + n;
    }
  };

  cvm.item = (x) =>
    typeof x === "string"
      ? { hash: cvm.hex(x), data: new Uint8Array() }
      : {
          hash: cvm.hex(x.hash),
          data: cvm.bytes(x.data ?? new Uint8Array()),
        };

  cvm.buildBlock = (items) => {
    items = items.map(cvm.item);

    const out = new Uint8Array(
      items.reduce((n, item) => n + 36 + item.data.length, 32)
    );

    let o = 0;

    for (const item of items) {
      out.set(cvm.unhex(item.hash), o);
      o += 32;

      cvm.writeU32(out, o, item.data.length);
      o += 4;

      out.set(item.data, o);
      o += item.data.length;
    }

    return out;
  };

  cvm.parseBlock = (file) => {
    file = cvm.bytes(file);

    if (!cvm.isBlockFile(file)) {
      throw new Error("not a module-set block");
    }

    const items = [];

    for (let o = 0; !cvm.zhash(file, o);) {
      const n = cvm.u32(file, o + 32);

      items.push({
        hash: cvm.hex(file.subarray(o, o + 32)),
        data: file.slice(o + 36, o + 36 + n),
      });

      o += 36 + n;
    }

    return items;
  };

  cvm.readHash = (o = cvm.PTR.off) =>
    cvm.PTR.buf.subarray(o, o + 32);

  cvm.dlen = (o = cvm.PTR.off) =>
    cvm.zhash(cvm.PTR.buf, o) ? 0 : cvm.u32(cvm.PTR.buf, o + 32);

  cvm.data = () =>
    cvm.PTR.buf.subarray(cvm.PTR.off + 36, cvm.PTR.off + 36 + cvm.dlen());

  cvm.parseBlockSafe = (file) => {
    try {
      file = file && file.length ? file : new Uint8Array(32);
      return cvm.parseBlock(file).map(cvm.item);
    } catch {
      return [];
    }
  };

  return cvm.resume();
}
"""


CORE_MEMORY_JS = r"""
{
  const cvm = CVM;

  cvm.std ??= new Uint8Array(1024);
  cvm.stdsize ??= 0;
  cvm.stdoffset ??= 0;

  cvm.stdEnsure = (need) => {
    if (cvm.std.length >= need) return;

    let n = cvm.std.length || 1024;
    while (n < need) n *= 2;

    const next = new Uint8Array(n);
    next.set(cvm.std);
    cvm.std = next;
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
    data = cvm.bytes(data);

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

  cvm.varKey = (id) => cvm.hex(id);

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
    const size = cvm.VSZ.get(k) ?? cvm.bytes(data).length;
    const next = new Uint8Array(size);

    next.set(cvm.bytes(data).subarray(0, size));

    cvm.VSZ.set(k, size);
    cvm.VAR.set(k, next);

    return next;
  };

  return cvm.resume();
}
"""


NET_API_TEMPLATE = r"""
{
  const cvm = CVM;
  const configuredBase = __CONFIGURED_BASE__;

  const pickBase = () => {
    let base = "";

    try {
      if (typeof apiBase !== "undefined" && apiBase) {
        base = apiBase;
      }
    } catch {}

    if (!base && globalThis.apiBase) {
      base = globalThis.apiBase;
    }

    if (!base && cvm.apiBase) {
      base = cvm.apiBase;
    }

    if (
      !base &&
      globalThis.location &&
      (location.protocol === "http:" || location.protocol === "https:") &&
      location.port === "9000"
    ) {
      base = location.origin;
    }

    if (!base) {
      base = configuredBase;
    }

    return String(base).replace(/\/+$/, "");
  };

  cvm.apiBase = pickBase();
  globalThis.apiBase = cvm.apiBase;

  cvm.apiURL = (path) =>
    cvm.apiBase + (String(path).startsWith("/") ? path : "/" + path);

  cvm.apiJSON = async (method, path, data, headers) => {
    const options = {
      method,
      headers: headers || {},
    };

    if (data !== undefined && data !== null) {
      options.body = data;
    }

    const res = await fetch(cvm.apiURL(path), options);
    const json = await res.json();

    if (!json.ok) {
      throw new Error(json.error || method + " " + path + " failed");
    }

    return json.data;
  };

  cvm.apiUpload = async (data) =>
    cvm.unhex((await cvm.apiJSON("POST", "/api/upload", cvm.bytes(data))).hash);

  cvm.apiChildren = async (parent) =>
    (await cvm.apiJSON("GET", "/api/children/" + cvm.hex(parent))).children || [];

  cvm.apiEdge = async (parent, child) =>
    cvm.apiJSON(
      "POST",
      "/api/edge/" + cvm.hex(parent) + "/" + cvm.hex(child),
      new Uint8Array()
    );

  cvm.apiVote = async (user, parent, child) =>
    cvm.apiJSON(
      "POST",
      "/api/vote/" + cvm.hex(user) + "/" + cvm.hex(parent) + "/" + cvm.hex(child),
      new Uint8Array()
    );

  cvm.apiUserGet = async (user, keyHash) =>
    cvm.unhex(
      (
        await cvm.apiJSON(
          "GET",
          "/api/user/get/" + cvm.hex(user) + "/" + cvm.hex(keyHash)
        )
      ).value
    );

  cvm.apiUserSet = async (user, keyHash, fileHash) =>
    cvm.apiJSON(
      "POST",
      "/api/user/set/" + cvm.hex(user) + "/" + cvm.hex(keyHash) + "/" + cvm.hex(fileHash),
      new Uint8Array()
    );

  cvm.apiDownload = async (hash) => {
    const res = await fetch(cvm.apiURL("/api/file/" + cvm.hex(hash)));

    if (!res.ok) {
      throw new Error("file not found: " + cvm.hex(hash));
    }

    return new Uint8Array(await res.arrayBuffer());
  };

  console.log("[CVM] apiBase =", cvm.apiBase);

  return cvm.resume();
}
"""


STORE_NAMED_JS = r"""
{
  const cvm = CVM;

  cvm.FC ??= new Map();
  cvm.HC ??= new Map();
  cvm.OV ??= new Map();
  cvm.ST ??= [];

  cvm.downloadCached = async (hash) => {
    const k = cvm.hex(hash);

    if (!cvm.FC.has(k)) {
      if (cvm.apiDownload) {
        cvm.FC.set(k, await cvm.apiDownload(hash));
      } else {
        cvm.FC.set(k, await cvm.download_file(hash));
      }
    }

    return cvm.FC.get(k);
  };

  cvm.userGet = async (keyHash) => {
    if (!cvm.USER) throw new Error("no user");
    return cvm.apiUserGet(cvm.USER, keyHash);
  };

  cvm.userSet = async (keyHash, fileHash) => {
    if (!cvm.USER) throw new Error("no user");
    return cvm.apiUserSet(cvm.USER, keyHash, fileHash);
  };

  cvm.gethashhashfile = async (keyHash) => {
    const k = cvm.hex(keyHash);

    if (cvm.OV.has(k)) {
      return cvm.OV.get(k);
    }

    if (!cvm.HC.has(k)) {
      let fileHash;

      if (cvm.USER) {
        try {
          fileHash = await cvm.userGet(keyHash);
        } catch {
          fileHash = await cvm.getfirstchild(keyHash);
        }
      } else {
        fileHash = await cvm.getfirstchild(keyHash);
      }

      cvm.HC.set(k, fileHash);
    }

    return cvm.downloadCached(cvm.HC.get(k));
  };

  cvm.override = (keyHash, file) => {
    cvm.OV.set(cvm.hex(keyHash), cvm.bytes(file));
  };

  cvm.Modify_override = async () => {
    if (!cvm.USER) return;

    for (const [keyHex, file] of [...cvm.OV]) {
      const fileHash = await cvm.apiUpload(file);

      await cvm.userSet(cvm.unhex(keyHex), fileHash);

      cvm.HC.set(keyHex, fileHash);
      cvm.FC.set(cvm.hex(fileHash), file);
    }

    cvm.OV.clear();
  };

  cvm.user = (userId) => {
    cvm.USER = cvm.hex(userId).trim().toLowerCase();
    cvm.HC.clear();
    return cvm.USER;
  };

  return cvm.resume();
}
"""


EXEC_BLOCK_JS = r"""
{
  const cvm = CVM;

  cvm.enterBlock = async (block) => {
    block = cvm.bytes(block);
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

  cvm.setprog = async (prog) => {
    cvm.PROG = prog.map(cvm.item);
    cvm.ROOT = cvm.buildBlock(cvm.PROG);
    cvm.override(await cvm.sha256("HTMLJSstart"), cvm.ROOT);
    return cvm.ROOT;
  };

  cvm.persistRoot = async () => {
    if (!cvm.ROOT) return;

    cvm.PROG = cvm.parseBlock(cvm.ROOT).map(cvm.item);
    cvm.override(await cvm.sha256("HTMLJSstart"), cvm.ROOT);

    try {
      await cvm.Modify_override();
    } catch (err) {
      console.warn("CVM persistRoot failed", err);
    }
  };

  cvm.resume = async () => {
    cvm.PTR.off += 36 + cvm.dlen();
    return cvm.executeBlock();
  };

  cvm.executeBlock = async () => {
    for (;;) {
      await cvm.Modify_override();

      if (cvm.zhash(cvm.PTR.buf, cvm.PTR.off)) {
        const prev = cvm.ST.pop();

        if (!prev) return;

        cvm.PTR = prev;
        return cvm.resume();
      }

      const file = await cvm.gethashhashfile(cvm.readHash());

      if (cvm.isBlockFile(file)) {
        cvm.ST.push({
          buf: cvm.PTR.buf,
          off: cvm.PTR.off,
        });

        cvm.PTR = {
          buf: file,
          off: 0,
        };

        continue;
      }

      return cvm.execute_call(cvm.textDecoder.decode(file));
    }
  };

  return cvm.resume();
}
"""


FLOW_DELAY_JS = r"""
{
  const cvm = CVM;
  const d = cvm.data();
  const ms = d.length >= 4 ? cvm.u32(d, 0) : 80;
  await cvm.sleep(ms);
  return cvm.resume();
}
"""


DOM_BASE_JS = r"""
{
  const cvm = CVM;

  cvm.esc = (text) => String(text ?? "").replace(/[&<>"']/g, (ch) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
  })[ch]);

  cvm.ensureStyle = (id, css) => {
    if (document.getElementById(id)) return;

    const style = document.createElement("style");
    style.id = id;
    style.textContent = css;
    document.head.appendChild(style);
  };

  cvm.ensureStyle("cvm-free-module-set-style", `
    .cvm2-panel {
      position: fixed;
      z-index: 99999;
      box-sizing: border-box;
      color: #271f1a;
      background: rgba(255, 253, 248, .96);
      border: 1px solid rgba(42, 33, 28, .78);
      border-radius: 18px;
      box-shadow: 0 18px 70px rgba(30, 20, 14, .16);
      font: 13px/1.45 ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
      resize: none;
    }

    .cvm2-head {
      display: flex;
      align-items: center;
      gap: 8px;
      min-height: 36px;
      padding: 8px 11px;
      cursor: move;
      user-select: none;
      border-bottom: 1px solid rgba(42, 33, 28, .14);
    }

    .cvm2-head b {
      font: 900 18px/1 system-ui, sans-serif;
      letter-spacing: -.04em;
    }

    .cvm2-head small {
      color: #aaa39d;
      font-weight: 800;
      font-size: 10px;
      letter-spacing: .13em;
      text-transform: uppercase;
      white-space: nowrap;
    }

    .cvm2-tools {
      margin-left: auto;
      display: inline-flex;
      gap: 6px;
      flex-wrap: wrap;
    }

    .cvm2-button,
    .cvm2-head button,
    .cvm2-forge button {
      color: #271f1a;
      background: #fff9ee;
      border: 1px solid rgba(42, 33, 28, .72);
      border-radius: 999px;
      padding: 3px 9px;
      font: 800 11px ui-monospace, monospace;
      cursor: pointer;
    }

    .cvm2-button:hover,
    .cvm2-head button:hover,
    .cvm2-forge button:hover {
      color: #fff9ee;
      background: #271f1a;
    }

    .cvm2-browser {
      left: 16px;
      top: 16px;
      width: 320px;
      max-height: calc(100vh - 32px);
      overflow: hidden;
    }

    .cvm2-browser-path {
      padding: 8px 11px 0;
      color: #8c8580;
      word-break: break-all;
    }

    .cvm2-browser-list {
      max-height: calc(100vh - 106px);
      overflow: auto;
      padding: 9px;
    }

    .cvm2-row {
      margin: 6px 0;
      padding: 8px 10px;
      background: #fffaf1;
      border: 1px solid rgba(42, 33, 28, .25);
      border-radius: 13px;
      cursor: grab;
      overflow: hidden;
      white-space: nowrap;
      text-overflow: ellipsis;
    }

    .cvm2-row:hover {
      background: #f3eadc;
      border-color: rgba(42, 33, 28, .72);
    }

    .cvm2-row small {
      color: #99908a;
      margin-left: 5px;
    }

    .cvm2-editor {
      right: 16px;
      top: 16px;
      width: min(1120px, calc(100vw - 360px));
      height: min(84vh, 820px);
      overflow: hidden;
      resize: none;
    }

    .cvm2-stage {
      position: relative;
      height: calc(100% - 53px);
      overflow: auto;
      background:
        radial-gradient(circle at 18px 18px, rgba(42,33,28,.16) 1px, transparent 1px),
        linear-gradient(135deg, #fffdf8, #fffaf2);
      background-size: 30px 30px, 100% 100%;
      cursor: default;
    }

    .cvm2-stage.middle-panning {
      cursor: grabbing;
      user-select: none;
    }

    .cvm2-lines {
      position: absolute;
      left: 0;
      top: 0;
      pointer-events: none;
      overflow: visible;
    }

    .cvm2-frame {
      position: absolute;
      box-sizing: border-box;
      width: 820px;
      height: 540px;
      background: rgba(255, 255, 255, .52);
      border: 1.5px solid rgba(42, 33, 28, .84);
      border-radius: 22px;
      box-shadow: 0 8px 28px rgba(30,20,14,.06);
      resize: none;
    }

    .cvm2-frame.expanded {
      width: 760px;
      height: 500px;
    }

    .cvm2-frame-head {
      position: absolute;
      left: 16px;
      right: 16px;
      top: -36px;
      display: flex;
      align-items: center;
      gap: 8px;
      cursor: move;
      user-select: none;
    }

    .cvm2-frame-mark {
      width: 22px;
      height: 22px;
      flex: none;
      border: 4px solid #2a211c;
      border-radius: 50%;
      box-shadow: inset 0 0 0 5px #fffdf8;
      background: #2a211c;
    }

    .cvm2-frame-title {
      font: 950 21px/1 system-ui, sans-serif;
      letter-spacing: -.045em;
      white-space: nowrap;
    }

    .cvm2-frame-sub {
      color: #aaa39d;
      font: 800 10px ui-monospace, monospace;
      letter-spacing: .13em;
      text-transform: uppercase;
      white-space: nowrap;
    }

    .cvm2-frame-body {
      position: absolute;
      inset: 34px 14px 14px 14px;
      overflow: visible;
    }

    .cvm2-frame.drop {
      background: rgba(255, 246, 225, .8);
      box-shadow: inset 0 0 0 2px rgba(42,33,28,.28);
    }

    .cvm2-node {
      position: absolute;
      box-sizing: border-box;
      width: 260px;
      min-height: 176px;
      padding: 11px 12px;
      color: #271f1a;
      background: rgba(255, 255, 252, .96);
      border: 1.4px solid rgba(42, 33, 28, .84);
      border-radius: 17px;
      box-shadow: 0 4px 16px rgba(30,20,14,.08);
      cursor: grab;
      user-select: none;
      resize: none;
    }

    .cvm2-node:hover {
      background: #fff7e6;
    }

    .cvm2-node.dragging {
      opacity: .68;
      cursor: grabbing;
    }

    .cvm2-node-main {
      display: flex;
      align-items: center;
      gap: 8px;
      min-width: 0;
    }

    .cvm2-node-icon {
      display: none;
      width: 25px;
      height: 25px;
      flex: none;
      color: #271f1a;
    }

    .cvm2-node.has-svg .cvm2-node-icon {
      display: grid;
      place-items: center;
    }

    .cvm2-node-icon svg {
      width: 25px;
      height: 25px;
      display: block;
    }

    .cvm2-node-name {
      min-width: 0;
      overflow: hidden;
      white-space: nowrap;
      text-overflow: ellipsis;
      font: 950 19px/1.05 system-ui, sans-serif;
      letter-spacing: -.04em;
    }

    .cvm2-node-desc {
      margin-top: 3px;
      color: #9b948e;
      font-size: 10px;
      font-weight: 800;
      letter-spacing: .08em;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }

    .cvm2-data {
      margin-top: 8px;
      padding-top: 7px;
      border-top: 1px solid rgba(42,33,28,.18);
      user-select: text;
      cursor: default;
    }

    .cvm2-data label {
      display: block;
      margin: 5px 0 3px;
      color: #8c8580;
      font-weight: 800;
      font-size: 10px;
      letter-spacing: .06em;
      text-transform: uppercase;
    }

    .cvm2-data input,
    .cvm2-data textarea,
    .cvm2-forge input,
    .cvm2-forge textarea {
      width: 100%;
      box-sizing: border-box;
      color: #271f1a;
      background: #fffaf1;
      border: 1px solid rgba(42,33,28,.58);
      border-radius: 9px;
      padding: 6px;
      font: 12px ui-monospace, monospace;
      resize: none;
    }

    .cvm2-data textarea {
      height: 42px;
      min-height: 42px;
      overflow: auto;
    }

    .cvm2-chip {
      display: inline-block;
      margin-left: 5px;
      padding: 1px 6px;
      border: 1px solid rgba(42,33,28,.3);
      border-radius: 999px;
      color: #7c746e;
      font-size: 10px;
      font-weight: 800;
    }

    .cvm2-add-hint {
      position: absolute;
      inset: 18px;
      display: none;
      place-items: center;
      border: 1px dashed rgba(42,33,28,.42);
      border-radius: 18px;
      color: #8c8580;
      background: rgba(255,255,255,.45);
      pointer-events: none;
      font-weight: 900;
    }

    .cvm2-stage.drop > .cvm2-add-hint {
      display: grid;
    }

    .cvm2-toast {
      position: fixed;
      left: 50%;
      top: 14px;
      z-index: 100001;
      transform: translateX(-50%);
      max-width: min(720px, calc(100vw - 40px));
      padding: 7px 16px;
      color: #271f1a;
      background: #fff3ce;
      border: 1px solid rgba(42,33,28,.75);
      border-radius: 999px;
      box-shadow: 0 10px 40px rgba(30,20,14,.16);
      font: 900 14px system-ui, sans-serif;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }

    .cvm2-forge {
      position: fixed;
      right: 24px;
      bottom: 24px;
      z-index: 100000;
      width: min(720px, calc(100vw - 48px));
      max-height: min(82vh, 760px);
      overflow: auto;
      background: rgba(255,253,248,.98);
      border: 1.5px solid rgba(42,33,28,.84);
      border-radius: 22px;
      box-shadow: 0 20px 72px rgba(30,20,14,.2);
      color: #271f1a;
      font: 13px/1.45 ui-monospace, monospace;
      resize: none;
    }

    .cvm2-forge-body {
      padding: 12px;
    }

    .cvm2-forge label {
      display: block;
      margin: 9px 0 4px;
      color: #8c8580;
      font-weight: 900;
    }

    .cvm2-forge textarea {
      min-height: 58px;
      resize: none;
    }

    .cvm2-forge-grid {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 9px;
    }

    .cvm2-forge-list {
      min-height: 130px;
      padding: 8px;
      background: #fffaf1;
      border: 1px dashed rgba(42,33,28,.4);
      border-radius: 15px;
    }

    .cvm2-mini {
      display: block;
      margin: 6px 0;
      padding: 7px;
      background: white;
      border: 1px solid rgba(42,33,28,.26);
      border-radius: 12px;
      cursor: grab;
    }

    .cvm2-mini-name {
      overflow: hidden;
      white-space: nowrap;
      text-overflow: ellipsis;
      font-weight: 900;
      margin-bottom: 5px;
    }

    #cvm-out {
      position: fixed;
      left: 50%;
      top: 14px;
      z-index: 99998;
      transform: translateX(-50%);
      padding: 6px 18px;
      color: #271f1a;
      background: #fff3ce;
      border: 1px solid rgba(42,33,28,.75);
      border-radius: 999px;
      font: 900 28px system-ui, sans-serif;
    }

    @media (max-width: 840px) {
      .cvm2-editor {
        left: 16px;
        right: 16px;
        top: 360px;
        width: calc(100vw - 32px);
      }

      .cvm2-forge-grid {
        grid-template-columns: 1fr;
      }
    }
  `);

  cvm.toast = (text, ms = 1600) => {
    let el = document.querySelector(".cvm2-toast");

    if (!el) {
      el = document.createElement("div");
      el.className = "cvm2-toast";
      document.body.appendChild(el);
    }

    el.textContent = text;
    clearTimeout(el.__timer);
    el.__timer = setTimeout(() => el.remove(), ms);
  };

  cvm.dragPanel = (panel, handle) => {
    let drag = null;

    handle.onmousedown = (event) => {
      if (event.button !== 0) return;
      if (event.target.closest("button,input,textarea,select")) return;

      const rect = panel.getBoundingClientRect();

      drag = {
        x: event.clientX,
        y: event.clientY,
        left: rect.left,
        top: rect.top,
      };

      panel.style.left = `${rect.left}px`;
      panel.style.top = `${rect.top}px`;
      panel.style.right = "auto";
      panel.style.bottom = "auto";

      event.preventDefault();
    };

    addEventListener("mousemove", (event) => {
      if (!drag) return;

      panel.style.left = `${drag.left + event.clientX - drag.x}px`;
      panel.style.top = `${drag.top + event.clientY - drag.y}px`;
    });

    addEventListener("mouseup", () => {
      drag = null;
    });
  };

  cvm.LIBS ??= {
    gsap: { url: "https://cdn.jsdelivr.net/npm/gsap@3.12.5/dist/gsap.min.js", global: "gsap" },
    anime: { url: "https://cdn.jsdelivr.net/npm/animejs@3.2.2/lib/anime.min.js", global: "anime" },
    matter: { url: "https://cdn.jsdelivr.net/npm/matter-js@0.20.0/build/matter.min.js", global: "Matter" },
    pixi: { url: "https://cdn.jsdelivr.net/npm/pixi.js@8.8.1/dist/pixi.min.js", global: "PIXI" },
    phaser: { url: "https://cdn.jsdelivr.net/npm/phaser@3.87.0/dist/phaser.min.js", global: "Phaser" },
    babylon: { url: "https://cdn.jsdelivr.net/npm/babylonjs@7.42.0/babylon.min.js", global: "BABYLON" },
    d3: { url: "https://cdn.jsdelivr.net/npm/d3@7.9.0/dist/d3.min.js", global: "d3" },
    three: { module: true, url: "https://cdn.jsdelivr.net/npm/three@0.171.0/build/three.module.js" },
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

  return cvm.resume();
}
"""


GRAPH_FREE_JS = r"""
{
  const cvm = CVM;

  cvm.layoutNS = () =>
    `CVM.freeLayout.${cvm.USER || "public"}`;

  cvm.layoutKey = (id) =>
    `${cvm.layoutNS()}.${id}`;

  cvm.layoutLoad = (id) => {
    try {
      const value = JSON.parse(localStorage.getItem(cvm.layoutKey(id)) || "{}");
      value.nodes ??= {};
      return value;
    } catch {
      return { nodes: {} };
    }
  };

  cvm.layoutSave = (id, value) => {
    value.nodes ??= {};
    localStorage.setItem(cvm.layoutKey(id), JSON.stringify(value));
  };

  cvm.defaultNodePos = (index) => ({
    x: 42 + (index % 3) * 285,
    y: 54 + Math.floor(index / 3) * 220,
  });

  cvm.dragInside = (el, handle, getPos, setPos, onMove, skip = "button,input,textarea,select") => {
    let drag = null;

    handle.onmousedown = (event) => {
      if (event.button !== 0) return;
      if (event.target.closest(skip)) return;

      const p = getPos();

      drag = {
        x: event.clientX,
        y: event.clientY,
        px: p.x,
        py: p.y,
      };

      el.classList.add("dragging");
      event.preventDefault();
      event.stopPropagation();
    };

    addEventListener("mousemove", (event) => {
      if (!drag) return;

      const pos = {
        x: Math.max(-2000, drag.px + event.clientX - drag.x),
        y: Math.max(-2000, drag.py + event.clientY - drag.y),
      };

      setPos(pos);
      onMove?.(pos);
    });

    addEventListener("mouseup", () => {
      if (!drag) return;
      drag = null;
      el.classList.remove("dragging");
    });
  };

  cvm.enableMiddlePan = (el) => {
    if (el.__cvmMiddlePan) return;
    el.__cvmMiddlePan = true;

    let pan = null;

    el.addEventListener("mousedown", (event) => {
      if (event.button !== 1) return;

      pan = {
        x: event.clientX,
        y: event.clientY,
        left: el.scrollLeft,
        top: el.scrollTop,
      };

      el.classList.add("middle-panning");
      event.preventDefault();
      event.stopPropagation();
    });

    addEventListener("mousemove", (event) => {
      if (!pan) return;

      el.scrollLeft = pan.left - (event.clientX - pan.x);
      el.scrollTop = pan.top - (event.clientY - pan.y);

      event.preventDefault();
    });

    addEventListener("mouseup", () => {
      if (!pan) return;

      pan = null;
      el.classList.remove("middle-panning");
    });

    el.addEventListener("auxclick", (event) => {
      if (event.button === 1) {
        event.preventDefault();
      }
    });
  };

  return cvm.resume();
}
"""


META_OPTIONAL_JS = r"""
{
  const cvm = CVM;

  cvm.META_CACHE ??= new Map();
  cvm.TAG_CACHE ??= new Map();

  cvm.shortHash = (hash) => `${cvm.hex(hash).slice(0, 10)}…`;

  cvm.directText = async (hash) => {
    try {
      const raw = await cvm.downloadCached(hash);
      const text = cvm.textDecoder.decode(raw).replace(/\s+/g, " ").trim();
      return text;
    } catch {
      return "";
    }
  };

  cvm.tagOf = async (hash) => {
    const h = cvm.hex(hash);

    if (cvm.TAG_CACHE.has(h)) return cvm.TAG_CACHE.get(h);

    let text = await cvm.directText(cvm.unhex(h));
    if (!text) text = cvm.shortHash(h);

    if (text.length > 80) text = text.slice(0, 80);

    cvm.TAG_CACHE.set(h, text);
    return text;
  };

  cvm.textByName = async (name) => {
    try {
      return cvm.textDecoder.decode(await cvm.gethashhashfile(await cvm.sha256(name)));
    } catch {
      return "";
    }
  };

  cvm.loadMeta = async (tag) => {
    if (cvm.META_CACHE.has(tag)) return cvm.META_CACHE.get(tag);

    const meta = {
      svg: (await cvm.textByName(`${tag}.svg`)).trim(),
      describe: (await cvm.textByName(`${tag}.describe`)).trim(),
      metersupport: (await cvm.textByName(`${tag}.metersupport`)).trim(),
    };

    cvm.META_CACHE.set(tag, meta);
    return meta;
  };

  cvm.metaForHash = async (hash) => {
    const tag = await cvm.tagOf(hash);
    return {
      tag,
      ...(await cvm.loadMeta(tag)),
    };
  };

  return cvm.resume();
}
"""


EDITOR_MODULESETS_JS = r"""
{
  const cvm = CVM;

  if (cvm.__freeModuleSetEditorV2) {
    return cvm.resume();
  }

  cvm.__freeModuleSetEditorV2 = true;

  document.querySelectorAll(".cvm2-browser,.cvm2-editor,.cvm2-forge").forEach((el) => el.remove());

  const emptyData = new Uint8Array();
  const zeroHash = "00".repeat(32);

  const state = {
    browserStack: [zeroHash],
    frames: new Map(),
    rendering: false,
  };

  const saveTimers = new Map();

  const nodeKey = (index, item) =>
    `${index}:${item.hash}`;

  const safeText = (data) => {
    try {
      return cvm.textDecoder.decode(data || emptyData);
    } catch {
      return "";
    }
  };

  const ensureUser = () => {
    if (cvm.USER) return cvm.USER;

    const id = prompt("user id");
    if (!id) throw new Error("need user id");

    return cvm.user(id.trim().toLowerCase());
  };

  const isSetHash = async (hash) => {
    try {
      const file = await cvm.gethashhashfile(cvm.unhex(cvm.hex(hash)));
      return cvm.isBlockFile(file);
    } catch {
      return false;
    }
  };

  const parseSetByHash = async (hash) => {
    const file = await cvm.gethashhashfile(cvm.unhex(cvm.hex(hash)));
    return cvm.parseBlock(file).map(cvm.item);
  };

  const uploadPublicFile = async (name, data) => {
    ensureUser();

    data = cvm.bytes(data);

    await cvm.apiUpload(name);

    const nameHash = await cvm.sha256(name);
    const fileHash = await cvm.apiUpload(data);

    await cvm.apiEdge(nameHash, fileHash);
    await cvm.apiVote(cvm.USER, nameHash, fileHash);

    cvm.HC.set(cvm.hex(nameHash), fileHash);
    cvm.FC.set(cvm.hex(fileHash), data);

    return {
      name,
      nameHash: cvm.hex(nameHash),
      fileHash: cvm.hex(fileHash),
    };
  };

  const publishRoot = async (tag) => {
    ensureUser();

    const tagHash = await cvm.sha256(tag);

    await cvm.apiEdge(zeroHash, tagHash);
    await cvm.apiVote(cvm.USER, zeroHash, tagHash);
  };

  const saveRootNow = async () => {
    ensureUser();

    const root = state.frames.get("root");
    if (!root) return;

    cvm.PROG = root.prog.map(cvm.item);
    cvm.ROOT = cvm.buildBlock(cvm.PROG);

    cvm.override(await cvm.sha256("HTMLJSstart"), cvm.ROOT);
    await cvm.Modify_override();
  };

  const saveFrameNow = async (frame) => {
    ensureUser();

    const file = cvm.buildBlock(frame.prog.map(cvm.item));

    cvm.override(cvm.unhex(frame.keyHash), file);
    await cvm.Modify_override();
  };

  const scheduleSave = (frame) => {
    clearTimeout(saveTimers.get(frame.id));

    saveTimers.set(frame.id, setTimeout(async () => {
      try {
        if (frame.root) {
          await saveRootNow();
        } else {
          await saveFrameNow(frame);
        }
      } catch (err) {
        console.warn("CVM autosave failed", err);
        cvm.toast("autosave failed: " + (err.message || err), 2600);
      }
    }, 320));
  };

  const loadRoot = async () => {
    const keyHash = cvm.hex(await cvm.sha256("HTMLJSstart"));
    const file = await cvm.gethashhashfile(cvm.unhex(keyHash));

    cvm.PROG = cvm.parseBlock(file).map(cvm.item);
    cvm.ROOT = cvm.buildBlock(cvm.PROG);

    state.frames.clear();

    state.frames.set("root", {
      id: "root",
      keyHash,
      title: "HTMLJSstart",
      subtitle: "VM FIRST RUN MODULE SET",
      prog: cvm.PROG,
      x: 54,
      y: 72,
      root: true,
    });
  };

  const makePanel = (className, title, subtitle, actionsHTML = "") => {
    const panel = document.createElement("div");
    panel.className = `cvm2-panel ${className}`;
    panel.innerHTML = `
      <div class="cvm2-head">
        <b>${cvm.esc(title)}</b>
        <small>${cvm.esc(subtitle || "")}</small>
        <span class="cvm2-tools">${actionsHTML}</span>
      </div>
    `;

    document.body.appendChild(panel);
    cvm.dragPanel(panel, panel.querySelector(".cvm2-head"));
    return panel;
  };

  const browser = makePanel(
    "cvm2-browser",
    "files",
    "module tree",
    `<button type="button" class="cvm2-up">上级</button>`
  );

  browser.insertAdjacentHTML("beforeend", `
    <div class="cvm2-browser-path"></div>
    <div class="cvm2-browser-list"></div>
  `);

  const editor = makePanel(
    "cvm2-editor",
    "module set editor",
    "middle-drag canvas",
    `
      <button type="button" class="cvm2-login">登录</button>
      <button type="button" class="cvm2-new-set">新建模块集</button>
    `
  );

  editor.insertAdjacentHTML("beforeend", `
    <div class="cvm2-stage">
      <svg class="cvm2-lines"></svg>
      <div class="cvm2-add-hint">拖入模块</div>
    </div>
  `);

  const browserPath = browser.querySelector(".cvm2-browser-path");
  const browserList = browser.querySelector(".cvm2-browser-list");
  const stage = editor.querySelector(".cvm2-stage");
  const svg = editor.querySelector(".cvm2-lines");

  cvm.enableMiddlePan(stage);

  const findFrameEl = (id) =>
    [...stage.querySelectorAll(".cvm2-frame")].find((el) => el.__frameId === id);

  const findNodeEl = (frameId, index) =>
    [...stage.querySelectorAll(".cvm2-node")].find((el) => el.__frameId === frameId && el.__index === index);

  const centerOf = (el) => {
    const sr = stage.getBoundingClientRect();
    const r = el.getBoundingClientRect();

    return {
      x: r.left - sr.left + stage.scrollLeft + r.width / 2,
      y: r.top - sr.top + stage.scrollTop + r.height / 2,
    };
  };

  const drawPath = (a, b, dashed = false) => {
    const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
    const mid = Math.max(30, Math.abs(b.x - a.x) / 2);

    path.setAttribute("d", `M ${a.x} ${a.y} C ${a.x + mid} ${a.y}, ${b.x - mid} ${b.y}, ${b.x} ${b.y}`);
    path.setAttribute("fill", "none");
    path.setAttribute("stroke", "#2a211c");
    path.setAttribute("stroke-width", dashed ? "1" : "1.4");
    path.setAttribute("opacity", dashed ? ".42" : ".78");

    if (dashed) {
      path.setAttribute("stroke-dasharray", "6 5");
    }

    svg.appendChild(path);
  };

  const redrawLines = () => {
    svg.innerHTML = "";

    const w = Math.max(stage.scrollWidth, stage.clientWidth, 3200);
    const h = Math.max(stage.scrollHeight, stage.clientHeight, 2200);

    svg.setAttribute("width", String(w));
    svg.setAttribute("height", String(h));
    svg.style.width = `${w}px`;
    svg.style.height = `${h}px`;

    for (const frame of state.frames.values()) {
      for (let i = 1; i < frame.prog.length; i++) {
        const a = findNodeEl(frame.id, i - 1);
        const b = findNodeEl(frame.id, i);

        if (a && b) drawPath(centerOf(a), centerOf(b), false);
      }

      if (frame.parent) {
        const parentNode = findNodeEl(frame.parent.frameId, frame.parent.index);
        const frameEl = findFrameEl(frame.id);

        if (parentNode && frameEl) drawPath(centerOf(parentNode), centerOf(frameEl), true);
      }
    }
  };

  const renderRawDataEditor = (body, frame, index, item) => {
    body.innerHTML = `
      <label>data text</label>
      <textarea class="cvm2-data-text" spellcheck="false">${cvm.esc(safeText(item.data || emptyData))}</textarea>
      <label>data hex</label>
      <textarea class="cvm2-data-hex" spellcheck="false">${cvm.esc(cvm.hex(item.data || emptyData))}</textarea>
    `;

    const textInput = body.querySelector(".cvm2-data-text");
    const hexInput = body.querySelector(".cvm2-data-hex");

    let lock = false;

    const commit = () => {
      frame.prog[index] = cvm.item(item);
      scheduleSave(frame);
      redrawLines();
    };

    textInput.oninput = () => {
      if (lock) return;

      lock = true;
      item.data = cvm.bytes(textInput.value);
      hexInput.value = cvm.hex(item.data);
      lock = false;

      commit();
    };

    hexInput.oninput = () => {
      if (lock) return;

      lock = true;
      item.data = cvm.unhex(hexInput.value);
      textInput.value = safeText(item.data);
      lock = false;

      commit();
    };
  };

  const renderDataEditor = async (body, frame, index, item, meta) => {
    const commit = async () => {
      frame.prog[index] = cvm.item(item);
      scheduleSave(frame);
      redrawLines();
    };

    if (meta.metersupport) {
      try {
        const fn = eval(`(${meta.metersupport})`);

        await fn({
          cvm,
          tag: meta.tag,
          item,
          body,
          state: body,
          api: {
            esc: cvm.esc,
            bytes: cvm.bytes,
            concat: cvm.concat,
            u32: cvm.u32,
            w32: cvm.u32bytes,
            unhex: cvm.unhex,
            decoder: cvm.textDecoder,
            encoder: cvm.textEncoder,
            emptyData,
            parseBlockSafe: cvm.parseBlockSafe,
            commit,
            lib: cvm.lib,
          },
        });

        return;
      } catch (err) {
        console.warn("metersupport failed", meta.tag, err);
        body.innerHTML = `<div style="color:#b33;font-weight:900">metersupport failed</div>`;
      }
    }

    renderRawDataEditor(body, frame, index, item);
  };

  const renderFrame = async (frame) => {
    const layout = cvm.layoutLoad(frame.id);
    layout.nodes ??= {};

    if (layout.frame) {
      frame.x = layout.frame.x ?? frame.x;
      frame.y = layout.frame.y ?? frame.y;
    }

    const frameEl = document.createElement("div");
    frameEl.className = `cvm2-frame ${frame.root ? "" : "expanded"}`;
    frameEl.__frameId = frame.id;
    frameEl.style.left = `${frame.x}px`;
    frameEl.style.top = `${frame.y}px`;

    frameEl.innerHTML = `
      <div class="cvm2-frame-head" title="${frame.root ? "拖动窗口" : "拖动窗口，双击关闭"}">
        <span class="cvm2-frame-mark"></span>
        <span class="cvm2-frame-title">${cvm.esc(frame.title)}</span>
        <span class="cvm2-frame-sub">${cvm.esc(frame.subtitle || "module set")}</span>
      </div>
      <div class="cvm2-frame-body"></div>
    `;

    stage.appendChild(frameEl);

    const head = frameEl.querySelector(".cvm2-frame-head");
    const body = frameEl.querySelector(".cvm2-frame-body");

    const saveLayout = () => {
      layout.frame = {
        x: frame.x,
        y: frame.y,
      };
      cvm.layoutSave(frame.id, layout);
    };

    cvm.dragInside(
      frameEl,
      head,
      () => ({ x: frame.x, y: frame.y }),
      (pos) => {
        frame.x = pos.x;
        frame.y = pos.y;
        frameEl.style.left = `${pos.x}px`;
        frameEl.style.top = `${pos.y}px`;
      },
      () => {
        saveLayout();
        redrawLines();
      }
    );

    head.ondblclick = () => {
      if (frame.root) return;
      state.frames.delete(frame.id);
      renderEditor();
    };

    body.ondragover = (event) => {
      event.preventDefault();
      frameEl.classList.add("drop");
    };

    body.ondragleave = (event) => {
      if (!frameEl.contains(event.relatedTarget)) {
        frameEl.classList.remove("drop");
      }
    };

    body.ondrop = async (event) => {
      event.preventDefault();
      frameEl.classList.remove("drop");

      const incomingHash = event.dataTransfer.getData("text/plain");
      if (!incomingHash) return;

      const rect = body.getBoundingClientRect();
      const item = {
        hash: incomingHash,
        data: emptyData,
      };

      const index = frame.prog.length;
      frame.prog.push(item);

      layout.nodes[nodeKey(index, item)] = {
        x: event.clientX - rect.left - 130,
        y: event.clientY - rect.top - 70,
      };

      cvm.layoutSave(frame.id, layout);
      scheduleSave(frame);

      await renderEditor();
    };

    for (let index = 0; index < frame.prog.length; index++) {
      const item = cvm.item(frame.prog[index]);
      frame.prog[index] = item;

      const meta = await cvm.metaForHash(item.hash);
      const isSet = await isSetHash(item.hash);
      const nk = nodeKey(index, item);
      const pos = layout.nodes[nk] || cvm.defaultNodePos(index);

      layout.nodes[nk] = pos;

      const node = document.createElement("div");
      node.className = `cvm2-node ${meta.svg ? "has-svg" : ""}`;
      node.__frameId = frame.id;
      node.__index = index;
      node.style.left = `${pos.x}px`;
      node.style.top = `${pos.y}px`;
      node.title = isSet ? "双击展开模块集" : "";

      node.innerHTML = `
        <div class="cvm2-node-main">
          <div class="cvm2-node-icon">${meta.svg || ""}</div>
          <div class="cvm2-node-name">${cvm.esc(meta.tag)}</div>
        </div>
        <div class="cvm2-node-desc">
          ${cvm.esc(meta.describe || (isSet ? "module set · double click" : "module"))}
          <span class="cvm2-chip">${item.hash.slice(0, 8)}</span>
        </div>
        <div class="cvm2-data"></div>
      `;

      body.appendChild(node);

      cvm.dragInside(
        node,
        node,
        () => layout.nodes[nk],
        (p) => {
          layout.nodes[nk] = p;
          node.style.left = `${p.x}px`;
          node.style.top = `${p.y}px`;
        },
        () => {
          cvm.layoutSave(frame.id, layout);
          redrawLines();
        }
      );

      node.ondblclick = async (event) => {
        if (event.target.closest("input,textarea,select")) return;
        if (!isSet) return;

        await openSetFrame(item.hash, {
          title: meta.tag,
          parent: {
            frameId: frame.id,
            index,
          },
          x: frame.x + 880,
          y: frame.y + 64 + index * 28,
        });
      };

      await renderDataEditor(node.querySelector(".cvm2-data"), frame, index, item, meta);
    }

    cvm.layoutSave(frame.id, layout);
  };

  async function openSetFrame(keyHash, options = {}) {
    keyHash = cvm.hex(keyHash);
    const id = `set:${keyHash}`;

    if (state.frames.has(id)) {
      cvm.toast("模块集已经展开");
      return;
    }

    const prog = await parseSetByHash(keyHash);

    const frame = {
      id,
      keyHash,
      title: options.title || await cvm.tagOf(keyHash),
      subtitle: "EXPANDED MODULE SET",
      prog,
      x: options.x ?? 960,
      y: options.y ?? 100,
      parent: options.parent,
      root: false,
    };

    state.frames.set(id, frame);
    await renderEditor();
  }

  async function renderEditor() {
    if (state.rendering) return;
    state.rendering = true;

    try {
      stage.querySelectorAll(".cvm2-frame").forEach((el) => el.remove());
      svg.innerHTML = "";

      for (const frame of state.frames.values()) {
        await renderFrame(frame);
      }

      redrawLines();
    } finally {
      state.rendering = false;
    }
  }

  async function renderBrowser() {
    const current = state.browserStack.at(-1);

    browserPath.textContent = state.browserStack.map((x) => x.slice(0, 8)).join("/");
    browserList.innerHTML = "";

    for (const child of await cvm.apiChildren(current)) {
      const tag = await cvm.tagOf(child.hash);
      const set = await isSetHash(child.hash);

      const row = document.createElement("div");
      row.className = "cvm2-row";
      row.draggable = true;
      row.innerHTML = `
        ${cvm.esc(tag)}
        <small>[${child.score}]</small>
        ${set ? `<span class="cvm2-chip">set</span>` : ""}
      `;

      row.ondragstart = (event) => {
        event.dataTransfer.effectAllowed = "copy";
        event.dataTransfer.setData("text/plain", child.hash);
      };

      row.onclick = () => {
        state.browserStack.push(child.hash);
        renderBrowser();
      };

      browserList.appendChild(row);
    }
  }

  const openForge = () => {
    let forge = document.querySelector(".cvm2-forge");

    if (forge) {
      forge.style.display = "";
      return;
    }

    let forgeProg = [];

    forge = document.createElement("div");
    forge.className = "cvm2-forge";
    forge.innerHTML = `
      <div class="cvm2-head">
        <b>new module set</b>
        <small>bin file</small>
        <span class="cvm2-tools">
          <button type="button" class="cvm2-forge-close">关闭</button>
        </span>
      </div>
      <div class="cvm2-forge-body">
        <label>模块集 tag，例如 my.bin</label>
        <input class="cvm2-forge-tag" placeholder="my.bin">

        <label>内部模块，左侧文件浏览器拖入；顺序就是执行顺序</label>
        <div class="cvm2-forge-list"></div>

        <div class="cvm2-forge-grid">
          <div>
            <label>svg，可选</label>
            <textarea class="cvm2-forge-svg" placeholder="不填则不上传"></textarea>
          </div>
          <div>
            <label>describe，可选</label>
            <textarea class="cvm2-forge-desc" placeholder="不填则不上传"></textarea>
          </div>
        </div>

        <label>metersupport，可选</label>
        <textarea class="cvm2-forge-meter" placeholder="async ({ cvm, item, body, api }) => { ... }"></textarea>

        <p class="cvm2-forge-state">ready</p>

        <button type="button" class="cvm2-forge-publish">发布到根目录</button>
        <button type="button" class="cvm2-forge-publish-add">发布并加入 HTMLJSstart</button>
      </div>
    `;

    document.body.appendChild(forge);
    cvm.dragPanel(forge, forge.querySelector(".cvm2-head"));

    const tagInput = forge.querySelector(".cvm2-forge-tag");
    const svgInput = forge.querySelector(".cvm2-forge-svg");
    const descInput = forge.querySelector(".cvm2-forge-desc");
    const meterInput = forge.querySelector(".cvm2-forge-meter");
    const list = forge.querySelector(".cvm2-forge-list");
    const forgeState = forge.querySelector(".cvm2-forge-state");

    const renderForge = async () => {
      list.innerHTML = "";

      if (!forgeProg.length) {
        list.innerHTML = `<div style="padding:12px;color:#8c8580;font-weight:900">空模块集。把左边文件拖进来。</div>`;
      }

      for (let i = 0; i < forgeProg.length; i++) {
        const item = cvm.item(forgeProg[i]);
        const tag = await cvm.tagOf(item.hash);

        const row = document.createElement("div");
        row.className = "cvm2-mini";
        row.draggable = true;
        row.innerHTML = `
          <div class="cvm2-mini-name">${i}. ${cvm.esc(tag)}</div>
          <label>data text</label>
          <textarea class="cvm2-mini-text" spellcheck="false">${cvm.esc(safeText(item.data || emptyData))}</textarea>
          <label>data hex</label>
          <textarea class="cvm2-mini-hex" spellcheck="false">${cvm.esc(cvm.hex(item.data || emptyData))}</textarea>
        `;

        row.ondragstart = (event) => {
          event.dataTransfer.setData("application/cvm-forge-index", String(i));
        };

        row.ondragover = (event) => {
          event.preventDefault();
        };

        row.ondrop = async (event) => {
          event.preventDefault();

          const from = event.dataTransfer.getData("application/cvm-forge-index");
          const hash = event.dataTransfer.getData("text/plain");

          if (from !== "") {
            const n = Number(from);
            const moved = forgeProg.splice(n, 1)[0];
            forgeProg.splice(i, 0, moved);
          } else if (hash) {
            forgeProg.splice(i, 0, {
              hash,
              data: emptyData,
            });
          }

          await renderForge();
        };

        const textInput = row.querySelector(".cvm2-mini-text");
        const hexInput = row.querySelector(".cvm2-mini-hex");

        let lock = false;

        textInput.oninput = () => {
          if (lock) return;

          lock = true;
          item.data = cvm.bytes(textInput.value);
          hexInput.value = cvm.hex(item.data);
          forgeProg[i] = item;
          lock = false;
        };

        hexInput.oninput = () => {
          if (lock) return;

          lock = true;
          item.data = cvm.unhex(hexInput.value);
          textInput.value = safeText(item.data);
          forgeProg[i] = item;
          lock = false;
        };

        list.appendChild(row);
      }
    };

    list.ondragover = (event) => {
      event.preventDefault();
    };

    list.ondrop = async (event) => {
      event.preventDefault();

      const from = event.dataTransfer.getData("application/cvm-forge-index");
      const hash = event.dataTransfer.getData("text/plain");

      if (from !== "") {
        const n = Number(from);
        const moved = forgeProg.splice(n, 1)[0];
        forgeProg.push(moved);
      } else if (hash) {
        forgeProg.push({
          hash,
          data: emptyData,
        });
      }

      await renderForge();
    };

    const publish = async (add) => {
      const tag = tagInput.value.trim();

      if (!/^[A-Za-z0-9_.:-]{1,64}$/.test(tag)) {
        forgeState.textContent = "tag 只能使用 A-Z a-z 0-9 _ . : -，长度 1-64";
        return;
      }

      try {
        forgeState.textContent = "publishing module set...";

        await uploadPublicFile(tag, cvm.buildBlock(forgeProg));

        if (svgInput.value.trim()) {
          await uploadPublicFile(`${tag}.svg`, svgInput.value);
        }

        if (descInput.value.trim()) {
          await uploadPublicFile(`${tag}.describe`, descInput.value);
        }

        if (meterInput.value.trim()) {
          await uploadPublicFile(`${tag}.metersupport`, meterInput.value);
        }

        await publishRoot(tag);

        cvm.META_CACHE?.delete(tag);
        cvm.TAG_CACHE?.delete(cvm.hex(await cvm.sha256(tag)));

        if (add) {
          const root = state.frames.get("root");
          const item = {
            hash: cvm.hex(await cvm.sha256(tag)),
            data: emptyData,
          };

          root.prog.push(item);

          const layout = cvm.layoutLoad(root.id);
          layout.nodes[nodeKey(root.prog.length - 1, item)] = cvm.defaultNodePos(root.prog.length - 1);
          cvm.layoutSave(root.id, layout);

          scheduleSave(root);
        }

        await renderBrowser();
        await renderEditor();

        forgeState.textContent = `published: ${tag}`;
      } catch (err) {
        console.warn("publish module set failed", err);
        forgeState.textContent = `failed: ${err.message || err}`;
      }
    };

    forge.querySelector(".cvm2-forge-close").onclick = () => {
      forge.style.display = "none";
    };

    forge.querySelector(".cvm2-forge-publish").onclick = () => publish(false);
    forge.querySelector(".cvm2-forge-publish-add").onclick = () => publish(true);

    renderForge();
  };

  browser.querySelector(".cvm2-up").onclick = () => {
    if (state.browserStack.length > 1) {
      state.browserStack.pop();
      renderBrowser();
    }
  };

  editor.querySelector(".cvm2-login").onclick = async () => {
    const id = prompt("user id");
    if (!id) return;

    cvm.user(id.trim().toLowerCase());

    await loadRoot();
    await renderBrowser();
    await renderEditor();

    cvm.toast("user loaded");
  };

  editor.querySelector(".cvm2-new-set").onclick = openForge;

  stage.ondragover = (event) => {
    if (event.target.closest(".cvm2-frame")) return;
    event.preventDefault();
    stage.classList.add("drop");
  };

  stage.ondragleave = (event) => {
    if (!stage.contains(event.relatedTarget)) {
      stage.classList.remove("drop");
    }
  };

  stage.ondrop = async (event) => {
    if (event.target.closest(".cvm2-frame")) return;

    event.preventDefault();
    stage.classList.remove("drop");

    const hash = event.dataTransfer.getData("text/plain");
    if (!hash) return;

    const root = state.frames.get("root");
    if (!root) return;

    const item = {
      hash,
      data: emptyData,
    };

    root.prog.push(item);

    const rootEl = findFrameEl(root.id);
    const body = rootEl?.querySelector(".cvm2-frame-body");
    const rect = body?.getBoundingClientRect();

    const layout = cvm.layoutLoad(root.id);
    layout.nodes[nodeKey(root.prog.length - 1, item)] = rect
      ? {
          x: event.clientX - rect.left - 130,
          y: event.clientY - rect.top - 70,
        }
      : cvm.defaultNodePos(root.prog.length - 1);

    cvm.layoutSave(root.id, layout);

    scheduleSave(root);
    await renderEditor();
  };

  cvm.openModuleSetForge = openForge;
  cvm.renderBrowser = renderBrowser;
  cvm.renderEditor = renderEditor;

  await loadRoot();
  await renderBrowser();
  await renderEditor();

  return cvm.resume();
}
"""


MODULES_JS = {
    "rerun": "CVM.PTR.off=0;return CVM.executeBlock();\n",

    "print": r"""
{
  const cvm = CVM;
  const d = cvm.data ? cvm.data() : new Uint8Array();
  const dec = cvm.textDecoder || new TextDecoder();
  const text = d.length ? dec.decode(d) : "hello world";

  if (cvm.out) {
    cvm.out(text);
  } else {
    let output = document.getElementById("cvm-out");

    if (!output) {
      output = document.createElement("div");
      output.id = "cvm-out";
      document.body.appendChild(output);
    }

    output.textContent = text;
  }

  return cvm.resume();
}
""",

    "setsize": r"""
{
  const cvm = CVM;
  const d = cvm.data();

  if (d.length >= 4) {
    const id = d.slice(0, d.length - 4);
    const size = new DataView(d.buffer, d.byteOffset + d.length - 4, 4).getUint32(0, true);
    cvm.setVarSize(id, size);
  }

  return cvm.resume();
}
""",

    "getvar": r"""
{
  const cvm = CVM;
  const id = cvm.data();
  const value = cvm.getVar(id);
  cvm.stdReturn(value);
  return cvm.resume();
}
""",

    "setvar": r"""
{
  const cvm = CVM;
  const id = cvm.data();
  const size = cvm.VSZ.get(cvm.varKey(id)) ?? 0;
  cvm.stdInput();
  const value = cvm.stdRead(size);
  cvm.setVar(id, value);
  return cvm.resume();
}
""",

    "IF": r"""
{
  const cvm = CVM;
  const program = cvm.data();

  if (!cvm.stdBool()) {
    return cvm.resume();
  }

  return cvm.enterBlock(program);
}
""",

    "IFrerun": r"""
{
  const cvm = CVM;

  if (cvm.stdBool()) {
    cvm.PTR.off = 0;
    return cvm.executeBlock();
  }

  return cvm.resume();
}
""",

    "Runonece": r"""
{
  const cvm = CVM;
  const d = cvm.data();

  if (!d.length || !d[0]) {
    return cvm.resume();
  }

  d[0] = 0;
  await cvm.persistRoot();

  return cvm.enterBlock(d.subarray(1));
}
""",

    "Runonce": r"""
{
  const cvm = CVM;
  const d = cvm.data();

  if (!d.length || !d[0]) {
    return cvm.resume();
  }

  d[0] = 0;
  await cvm.persistRoot();

  return cvm.enterBlock(d.subarray(1));
}
""",
}


PHYSICS_JS = {
    "physicsWorld": "{ const cvm = CVM; const Matter = await cvm.lib('matter'); cvm.world ??= {}; const physics = cvm.world.physics ??= {}; physics.defaults ??= { ball: { radius: 24, restitution: 0.86, frictionAir: 0.01, color: '#89dceb' }, gravity: { x: 0, y: 1 } }; if (!physics.engine) { physics.engine = Matter.Engine.create(); physics.engine.gravity.x = physics.defaults.gravity.x; physics.engine.gravity.y = physics.defaults.gravity.y; physics.bodies = new Map(); physics.bounds = []; } return cvm.resume(); }",
    "renderPhysics": "{ const cvm = CVM; const Matter = await cvm.lib('matter'); cvm.world ??= {}; const physics = cvm.world.physics ??= {}; if (!physics.engine) return cvm.resume(); let panel = document.getElementById('cvm-physics-stage'); if (!panel) { panel = document.createElement('div'); panel.id = 'cvm-physics-stage'; panel.style.cssText = 'position:fixed;left:16px;bottom:16px;z-index:99997;width:520px;height:300px;background:#111827;border:1px solid #7aa2f7;box-shadow:0 0 24px rgba(122,162,247,.22);overflow:hidden'; document.body.appendChild(panel); } const width = panel.clientWidth || 520, height = panel.clientHeight || 300; if (!physics.boundsReady) { const wallStyle = { fillStyle: '#293241', strokeStyle: '#7aa2f7', lineWidth: 1 }; physics.bounds = [Matter.Bodies.rectangle(width/2, height+10, width, 20, {isStatic:true, render:wallStyle}), Matter.Bodies.rectangle(width/2, -10, width, 20, {isStatic:true, render:wallStyle}), Matter.Bodies.rectangle(-10, height/2, 20, height, {isStatic:true, render:wallStyle}), Matter.Bodies.rectangle(width+10, height/2, 20, height, {isStatic:true, render:wallStyle})]; Matter.Composite.add(physics.engine.world, physics.bounds); physics.boundsReady = true; } if (!physics.render) { physics.render = Matter.Render.create({ element: panel, engine: physics.engine, options: { width, height, wireframes: false, background: '#111827', pixelRatio: window.devicePixelRatio || 1 } }); physics.runner = Matter.Runner.create(); Matter.Render.run(physics.render); Matter.Runner.run(physics.runner, physics.engine); } return cvm.resume(); }",
    "spawnBall": "{ const cvm = CVM; const Matter = await cvm.lib('matter'); cvm.world ??= {}; const physics = cvm.world.physics ??= {}; if (!physics.engine) return cvm.resume(); physics.bodies ??= new Map(); const cfg = physics.defaults.ball; const x = 80 + Math.random() * 340, y = 36 + Math.random() * 42; const ball = Matter.Bodies.circle(x, y, cfg.radius, { restitution: cfg.restitution, frictionAir: cfg.frictionAir, render: { fillStyle: cfg.color, strokeStyle: '#f4f7ff', lineWidth: 2 } }); Matter.Body.setVelocity(ball, { x: -5 + Math.random() * 10, y: -2 + Math.random() * 3 }); Matter.Composite.add(physics.engine.world, ball); physics.bodies.set(`ball:${Date.now()}:${Math.random()}`, ball); return cvm.resume(); }",
    "kickPhysics": "{ const cvm = CVM; const Matter = await cvm.lib('matter'); const bodies = cvm.world?.physics?.bodies; if (bodies) { for (const body of bodies.values()) { Matter.Body.applyForce(body, body.position, { x: (Math.random() - 0.5) * 0.08, y: -0.08 - Math.random() * 0.08 }); } } return cvm.resume(); }",
    "clearPhysics": "{ const cvm = CVM; const Matter = await cvm.lib('matter'); const physics = cvm.world?.physics; if (physics?.engine && physics?.bodies) { for (const body of physics.bodies.values()) { Matter.Composite.remove(physics.engine.world, body); } physics.bodies.clear(); } return cvm.resume(); }",
    "flipGravity": "{ const cvm = CVM; const physics = cvm.world?.physics; if (physics?.engine) { physics.engine.gravity.y = physics.engine.gravity.y >= 0 ? -1 : 1; physics.defaults ??= {}; physics.defaults.gravity = { x: physics.engine.gravity.x, y: physics.engine.gravity.y }; } return cvm.resume(); }",
}


PRINT_METER = r"""
async ({ item, body, api }) => {
  const value = api.decoder.decode(item.data || api.emptyData);

  body.innerHTML = `
    <label>弹出文本</label>
    <textarea class="cvm2-print-text" spellcheck="false"></textarea>
  `;

  const input = body.querySelector(".cvm2-print-text");
  input.value = value || "hello world";

  input.oninput = () => {
    item.data = api.encoder.encode(input.value);
    api.commit();
  };
}
"""


SETSIZE_METER = r"""
async ({ item, body, api }) => {
  const d = item.data || api.emptyData;
  const id = d.length >= 4 ? api.decoder.decode(d.slice(0, -4)) : "";
  const size = d.length >= 4 ? api.u32(d, d.length - 4) : 0;

  body.innerHTML = `
    <label>变量 id</label>
    <input class="cvm2-var-id" spellcheck="false">
    <label>变量大小 uint32</label>
    <input class="cvm2-var-size" type="number" min="0" step="1">
  `;

  const idInput = body.querySelector(".cvm2-var-id");
  const sizeInput = body.querySelector(".cvm2-var-size");

  idInput.value = id;
  sizeInput.value = String(size);

  const update = () => {
    item.data = api.concat(
      api.encoder.encode(idInput.value),
      api.w32(Number(sizeInput.value) || 0)
    );

    api.commit();
  };

  idInput.oninput = update;
  sizeInput.oninput = update;
}
"""


VAR_ID_METER = r"""
async ({ item, body, api, tag }) => {
  body.innerHTML = `
    <label>${api.esc(tag)} 变量 id</label>
    <input class="cvm2-var-id" spellcheck="false">
  `;

  const input = body.querySelector(".cvm2-var-id");
  input.value = api.decoder.decode(item.data || api.emptyData);

  input.oninput = () => {
    item.data = api.encoder.encode(input.value);
    api.commit();
  };
}
"""


DELAY_METER = r"""
async ({ item, body, api }) => {
  const d = item.data || api.emptyData;
  const ms = d.length >= 4 ? api.u32(d, 0) : 80;

  body.innerHTML = `
    <label>延迟毫秒 uint32</label>
    <input class="cvm2-delay-ms" type="number" min="0" step="1">
  `;

  const input = body.querySelector(".cvm2-delay-ms");
  input.value = String(ms);

  input.oninput = () => {
    item.data = api.w32(Number(input.value) || 0);
    api.commit();
  };
}
"""


IFRERUN_METER = r"""
async ({ body }) => {
  body.innerHTML = `
    <div style="padding:7px 2px;color:#8c8580;font-weight:900">
      无节点参数 data。<br>
      <span style="font-weight:700;font-size:11px">
        运行时读取 std 第一个 bool，为 true 则重新执行当前模块集。
      </span>
    </div>
  `;
}
"""


IF_METER = r"""
async ({ cvm, item, body, api }) => {
  let prog = api.parseBlockSafe(item.data || api.emptyData);

  const move = (xs, from, to) => {
    if (from < 0 || to < 0 || from === to) return;
    const it = xs.splice(from, 1)[0];
    xs.splice(Math.max(0, Math.min(to, xs.length)), 0, it);
  };

  const save = () => {
    item.data = cvm.buildBlock(prog);
    api.commit();
  };

  const render = async () => {
    body.innerHTML = `
      <label>IF 内部模块集</label>
      <div class="cvm2-if-list"
        style="min-height:48px;padding:6px;border:1px dashed rgba(42,33,28,.35);border-radius:10px;background:#fffaf1">
      </div>
      <div style="margin-top:5px;color:#8c8580;font-size:11px;font-weight:800">
        std bool 为 true 时执行。可从左侧拖入模块；拖动行可改变顺序。
      </div>
    `;

    const list = body.querySelector(".cvm2-if-list");

    if (!prog.length) {
      list.innerHTML = `<div style="color:#8c8580;font-weight:900">空内部模块集</div>`;
    }

    for (let i = 0; i < prog.length; i++) {
      const rowItem = cvm.item(prog[i]);
      const tag = await cvm.tagOf(rowItem.hash);

      const row = document.createElement("div");
      row.draggable = true;
      row.style.cssText = `
        margin:4px 0;
        padding:5px 7px;
        border:1px solid rgba(42,33,28,.25);
        border-radius:9px;
        background:white;
        cursor:grab;
        overflow:hidden;
        white-space:nowrap;
        text-overflow:ellipsis;
        font-weight:900;
      `;

      row.textContent = `${i}. ${tag}`;

      row.ondragstart = (event) => {
        event.dataTransfer.setData("application/cvm-meter-index", String(i));
      };

      row.ondragover = (event) => {
        event.preventDefault();
      };

      row.ondrop = async (event) => {
        event.preventDefault();

        const from = event.dataTransfer.getData("application/cvm-meter-index");
        const hash = event.dataTransfer.getData("text/plain");

        if (from !== "") {
          move(prog, Number(from), i);
        } else if (hash) {
          prog.splice(i, 0, { hash, data: api.emptyData });
        }

        save();
        await render();
      };

      list.appendChild(row);
    }

    list.ondragover = (event) => {
      event.preventDefault();
    };

    list.ondrop = async (event) => {
      event.preventDefault();

      const from = event.dataTransfer.getData("application/cvm-meter-index");
      const hash = event.dataTransfer.getData("text/plain");

      if (from !== "") {
        const n = Number(from);
        const moved = prog.splice(n, 1)[0];
        prog.push(moved);
      } else if (hash) {
        prog.push({ hash, data: api.emptyData });
      }

      save();
      await render();
    };
  };

  await render();
}
"""


RUNONCE_METER = r"""
async ({ cvm, item, body, api, tag }) => {
  const d = item.data || api.emptyData;
  let enabled = !!d[0];
  let prog = api.parseBlockSafe(d.slice(1));

  const move = (xs, from, to) => {
    if (from < 0 || to < 0 || from === to) return;
    const it = xs.splice(from, 1)[0];
    xs.splice(Math.max(0, Math.min(to, xs.length)), 0, it);
  };

  const save = () => {
    item.data = api.concat(
      new Uint8Array([enabled ? 1 : 0]),
      cvm.buildBlock(prog)
    );

    api.commit();
  };

  const render = async () => {
    body.innerHTML = `
      <label>
        <input class="cvm2-run-enabled" type="checkbox" style="width:auto">
        执行一次
      </label>

      <label>${api.esc(tag)} 内部模块集</label>
      <div class="cvm2-run-list"
        style="min-height:48px;padding:6px;border:1px dashed rgba(42,33,28,.35);border-radius:10px;background:#fffaf1">
      </div>

      <div style="margin-top:5px;color:#8c8580;font-size:11px;font-weight:800">
        第一个字节是 enabled，后面是内部模块集 block。
      </div>
    `;

    const checkbox = body.querySelector(".cvm2-run-enabled");
    const list = body.querySelector(".cvm2-run-list");

    checkbox.checked = enabled;

    checkbox.onchange = () => {
      enabled = checkbox.checked;
      save();
    };

    if (!prog.length) {
      list.innerHTML = `<div style="color:#8c8580;font-weight:900">空内部模块集</div>`;
    }

    for (let i = 0; i < prog.length; i++) {
      const rowItem = cvm.item(prog[i]);
      const name = await cvm.tagOf(rowItem.hash);

      const row = document.createElement("div");
      row.draggable = true;
      row.style.cssText = `
        margin:4px 0;
        padding:5px 7px;
        border:1px solid rgba(42,33,28,.25);
        border-radius:9px;
        background:white;
        cursor:grab;
        overflow:hidden;
        white-space:nowrap;
        text-overflow:ellipsis;
        font-weight:900;
      `;

      row.textContent = `${i}. ${name}`;

      row.ondragstart = (event) => {
        event.dataTransfer.setData("application/cvm-meter-index", String(i));
      };

      row.ondragover = (event) => {
        event.preventDefault();
      };

      row.ondrop = async (event) => {
        event.preventDefault();

        const from = event.dataTransfer.getData("application/cvm-meter-index");
        const hash = event.dataTransfer.getData("text/plain");

        if (from !== "") {
          move(prog, Number(from), i);
        } else if (hash) {
          prog.splice(i, 0, { hash, data: api.emptyData });
        }

        save();
        await render();
      };

      list.appendChild(row);
    }

    list.ondragover = (event) => {
      event.preventDefault();
    };

    list.ondrop = async (event) => {
      event.preventDefault();

      const from = event.dataTransfer.getData("application/cvm-meter-index");
      const hash = event.dataTransfer.getData("text/plain");

      if (from !== "") {
        const n = Number(from);
        const moved = prog.splice(n, 1)[0];
        prog.push(moved);
      } else if (hash) {
        prog.push({ hash, data: api.emptyData });
      }

      save();
      await render();
    };
  };

  await render();
}
"""


PHYSICSWORLD_METER = r"""
async ({ cvm, body, api }) => {
  const { esc } = api;

  cvm.world ??= {};
  const physics = cvm.world.physics ??= {};

  physics.defaults ??= {
    ball: { radius: 24, restitution: 0.86, frictionAir: 0.01, color: '#89dceb' },
    gravity: { x: 0, y: 1 }
  };

  const cfg = physics.defaults.ball;
  const g = physics.defaults.gravity;

  body.innerHTML = `
    <label>Radius</label>
    <input type="range" class="r" min="8" max="64" value="${cfg.radius}">
    <label>Bounce</label>
    <input type="range" class="b" min="0" max="1" step="0.01" value="${cfg.restitution}">
    <label>Gravity Y</label>
    <input type="range" class="g" min="-2" max="2" step="0.1" value="${g.y}">
    <label>Color</label>
    <input type="color" class="c" value="${esc(cfg.color)}">
  `;

  const sync = () => {
    cfg.radius = Number(body.querySelector(".r").value);
    cfg.restitution = Number(body.querySelector(".b").value);
    g.y = Number(body.querySelector(".g").value);
    cfg.color = body.querySelector(".c").value;

    if (physics.engine) {
      physics.engine.gravity.y = g.y;
    }
  };

  body.querySelectorAll("input").forEach((input) => {
    input.oninput = sync;
  });
}
"""


START_BIN_ITEMS = [
    "cvm.core.codec",
    "cvm.core.block",
    "cvm.core.memory",
    "cvm.net.api",
    "cvm.store.named",
    "cvm.exec.block",
    "cvm.dom.base",
    "cvm.graph.free",
    "cvm.meta.optional",
    "cvm.editor.moduleSets",
    ("cvm.flow.delay", le32(80)),
]

HTMLJSSTART_ITEMS = [
    "start.loader",
    "start.bin",
    "rerun",
]

BASE_BIN_ITEMS = [
    "setsize",
    "getvar",
    "setvar",
    "IF",
    "IFrerun",
    "Runonce",
]

PHYSICS_BIN_ITEMS = [
    "physicsWorld",
    "renderPhysics",
    "spawnBall",
    "kickPhysics",
    "clearPhysics",
    "flipGravity",
]


def make_net_api_js(base: str) -> str:
    return NET_API_TEMPLATE.replace("__CONFIGURED_BASE__", json.dumps(base.rstrip("/")))


def build_files(base: str):
    files = {}

    # 新启动系统：start.loader -> start.bin -> 通用基础模块。
    files["start.loader"] = LOADER_JS
    files["start"] = LOADER_JS
    files["cvm.core.codec"] = CORE_CODEC_JS
    files["cvm.core.block"] = CORE_BLOCK_JS
    files["cvm.core.memory"] = CORE_MEMORY_JS
    files["cvm.net.api"] = make_net_api_js(base)
    files["cvm.store.named"] = STORE_NAMED_JS
    files["cvm.exec.block"] = EXEC_BLOCK_JS
    files["cvm.flow.delay"] = FLOW_DELAY_JS
    files["cvm.dom.base"] = DOM_BASE_JS
    files["cvm.graph.free"] = GRAPH_FREE_JS
    files["cvm.meta.optional"] = META_OPTIONAL_JS
    files["cvm.editor.moduleSets"] = EDITOR_MODULESETS_JS

    # 基础模块。
    files.update(MODULES_JS)

    # 物理模块。
    files.update(PHYSICS_JS)

    # 模块集文件。
    files["start.bin"] = block(START_BIN_ITEMS)
    files["HTMLJSstart"] = block(HTMLJSSTART_ITEMS)
    files["base.bin"] = block(BASE_BIN_ITEMS)
    files["physics.bin"] = block(PHYSICS_BIN_ITEMS)

    # 描述。
    describes = {
        "HTMLJSstart.describe": "VM 首次运行模块集入口。",
        "start.loader.describe": "最小启动器。安装 block/JS 混合执行器，然后进入 start.bin。",
        "start.describe": "start.loader 的兼容别名。",
        "start.bin.describe": "启动模块集，由通用基础模块组成。",
        "base.bin.describe": "基础逻辑模块集。",
        "physics.bin.describe": "物理/游戏模块集。",

        "cvm.core.codec.describe": "通用编码模块：bytes、hex、unhex、u32、concat、sleep。",
        "cvm.core.block.describe": "通用模块集 block 编解码。",
        "cvm.core.memory.describe": "std 参数缓存和变量内存。",
        "cvm.net.api.describe": "HTTP API 封装。",
        "cvm.store.named.describe": "按名字 hash 获取/覆盖文件，支持用户私有覆盖。",
        "cvm.exec.block.describe": "block/JS 混合执行器。",
        "cvm.dom.base.describe": "DOM/CSS/UI 基础工具和库加载器。",
        "cvm.graph.free.describe": "自由节点布局、节点拖动、鼠标中键平移。",
        "cvm.meta.optional.describe": "可选 svg / describe / metersupport 元数据加载。",
        "cvm.editor.moduleSets.describe": "自由节点模块集编辑器。",
        "cvm.flow.delay.describe": "等待 data 中的 uint32 毫秒后继续执行。",

        "rerun.describe": "将当前 block 指针归零并重新执行。",
        "print.describe": "输出节点 data 文本；data 为空时输出 hello world。",
        "setsize.describe": "data 格式：变量 id + uint32 little-endian size。",
        "getvar.describe": "data 格式：变量 id。读取变量写入 std。",
        "setvar.describe": "data 格式：变量 id。从 std 读取数据写入变量。",
        "IF.describe": "data 格式：内部模块集 block。std bool 为 true 时执行。",
        "IFrerun.describe": "无 data。std bool 为 true 时重新执行当前模块集。",
        "Runonce.describe": "data 格式：enabled byte + 内部模块集 block。",
        "Runonece.describe": "Runonce 的旧拼写兼容。",

        "physicsWorld.describe": "创建 CVM.world.physics 和 Matter.js engine。",
        "renderPhysics.describe": "显示 Matter.js 物理舞台。",
        "spawnBall.describe": "生成一个物理小球。",
        "kickPhysics.describe": "给动态物体随机冲量。",
        "clearPhysics.describe": "清除动态物体。",
        "flipGravity.describe": "翻转重力方向。",
    }
    files.update(describes)

    # SVG 可选，这里给常用模块补默认图标。
    svg_names = [
        "HTMLJSstart", "start.loader", "start", "start.bin", "base.bin", "physics.bin",
        "cvm.core.codec", "cvm.core.block", "cvm.core.memory", "cvm.net.api",
        "cvm.store.named", "cvm.exec.block", "cvm.flow.delay", "cvm.dom.base",
        "cvm.graph.free", "cvm.meta.optional", "cvm.editor.moduleSets",
        "rerun", "print", "setsize", "getvar", "setvar", "IF", "IFrerun",
        "Runonce", "Runonece", "physicsWorld", "renderPhysics", "spawnBall",
        "kickPhysics", "clearPhysics", "flipGravity",
    ]
    for name in svg_names:
        files[f"{name}.svg"] = svg_for(name)

    # metersupport：真正决定节点 data 怎么显示/编辑。
    files["print.metersupport"] = PRINT_METER
    files["setsize.metersupport"] = SETSIZE_METER
    files["getvar.metersupport"] = VAR_ID_METER
    files["setvar.metersupport"] = VAR_ID_METER
    files["IF.metersupport"] = IF_METER
    files["IFrerun.metersupport"] = IFRERUN_METER
    files["Runonce.metersupport"] = RUNONCE_METER
    files["Runonece.metersupport"] = RUNONCE_METER
    files["cvm.flow.delay.metersupport"] = DELAY_METER
    files["physicsWorld.metersupport"] = PHYSICSWORLD_METER

    # 无节点参数的模块也给明确 data UI，避免全都显示 raw data。
    no_data_names = [
        "HTMLJSstart",
        "start.loader",
        "start",
        "start.bin",
        "base.bin",
        "physics.bin",
        "cvm.core.codec",
        "cvm.core.block",
        "cvm.core.memory",
        "cvm.net.api",
        "cvm.store.named",
        "cvm.exec.block",
        "cvm.dom.base",
        "cvm.graph.free",
        "cvm.meta.optional",
        "cvm.editor.moduleSets",
        "rerun",
        "renderPhysics",
        "spawnBall",
        "kickPhysics",
        "clearPhysics",
        "flipGravity",
    ]

    for name in no_data_names:
        files.setdefault(f"{name}.metersupport", no_data_meter(name))

    # 统一转 bytes。
    out = {}
    for name, data in files.items():
      if isinstance(data, bytes):
          out[name] = data
      else:
          out[name] = str(data).encode()

    return out


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default=BASE_DEFAULT)
    parser.add_argument("--id", default="id.bin")
    parser.add_argument("--write-index", default="", help="可选：写出修正后的 index.html")
    args = parser.parse_args()

    api = API(args.base)
    user = get_or_create_id(api, args.id)

    print(f"\n服务器: {args.base}")
    print(f"用户ID: {user}\n")

    if args.write_index:
        Path(args.write_index).write_text(make_index_html(args.base), encoding="utf-8")
        print(f"[+] wrote index: {args.write_index}")

    files = build_files(args.base)

    for name, data in files.items():
        put_if_changed(api, user, name, data)

    print("\n挂载根目录...")

    root_items = [
        "HTMLJSstart",
        "start.loader",
        "start",
        "start.bin",
        "base.bin",
        "physics.bin",

        "cvm.core.codec",
        "cvm.core.block",
        "cvm.core.memory",
        "cvm.net.api",
        "cvm.store.named",
        "cvm.exec.block",
        "cvm.flow.delay",
        "cvm.dom.base",
        "cvm.graph.free",
        "cvm.meta.optional",
        "cvm.editor.moduleSets",

        "rerun",
        "print",
        "setsize",
        "getvar",
        "setvar",
        "IF",
        "IFrerun",
        "Runonce",
        "Runonece",

        "physicsWorld",
        "renderPhysics",
        "spawnBall",
        "kickPhysics",
        "clearPhysics",
        "flipGravity",
    ]

    for name in root_items:
        mount_root(api, user, name)

    print("\n✅ CVM 单文件完整部署完成")
    print("入口结构：HTMLJSstart -> start.loader -> start.bin -> 通用模块")
    print("编辑器：自由节点；鼠标中键平移；节点左键拖动；数据直接显示；模块集双击展开")
    print("新建：创建模块集文件；svg / describe / metersupport 均可选")


if __name__ == "__main__":
    main()
