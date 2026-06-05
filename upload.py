#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import hashlib
import json
import re
import urllib.error
import urllib.request
from pathlib import Path

BASE_DEFAULT = "http://124.221.146.23:9000"
ZERO_HASH = b"\x00" * 32
ZERO_HEX = "00" * 32


def sha(data: bytes) -> bytes:
    return hashlib.sha256(data).digest()


def key(name: str) -> bytes:
    return sha(name.encode("utf-8"))


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
                data = data.encode("utf-8")
            data = data or b""

        h = key(name) if isinstance(name, str) else bytes.fromhex(name)
        out += h
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
    h = sha(data).hex()
    old = api.file(h)

    if old == data:
        return h

    got = api.upload(data)

    if got != h:
        raise RuntimeError("upload hash mismatch")

    return got


def first_child(api: API, parent: str):
    xs = api.children(parent)
    return xs[0]["hash"] if xs else None


def put(api: API, user: str, name: str, data: bytes):
    parent = key(name).hex()
    child = sha(data).hex()

    # key(name) 本身就是 name.encode() 的 sha。
    # 上传 name.encode() 后，浏览器可以直接按 key hash 下载到名字文本。
    ensure_direct_file(api, name.encode("utf-8"))

    cur = first_child(api, parent)

    if cur == child:
        print(f"[=] {name}")
        return child

    ensure_direct_file(api, data)
    api.edge(parent, child)
    api.vote(user, parent, child)

    print(f"{'[*]' if cur else '[+]'} {name} -> {child[:16]}...")
    return child


def mount_root(api: API, user: str, name: str):
    child = key(name).hex()
    existing = {x["hash"] for x in api.children(ZERO_HEX)}

    if child in existing:
        print(f"[=] root/{name}")
        return

    api.edge(ZERO_HEX, child)
    api.vote(user, ZERO_HEX, child)
    print(f"[+] root/{name}")


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
    h = String(h || "").trim().replace(/[^0-9a-f]/gi, "");
    if (h.length % 2) h = h.slice(0, -1);
    return new Uint8Array((h.match(/../g) || []).map((x) => parseInt(x, 16)));
  };

  const u32 = (b, o = 0) =>
    new DataView(b.buffer, b.byteOffset, b.byteLength).getUint32(o, true);

  const zhash = (b, o = 0) => {
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

  Object.assign(cvm, {
    bytes: cvm.bytes || bytes,
    hex: cvm.hex || hex,
    unhex: cvm.unhex || unhex,
    u32: cvm.u32 || u32,
    zhash: cvm.zhash || zhash,
    isBlockFile: cvm.isBlockFile || isBlockFile,
  });

  cvm.FC ??= new Map();
  cvm.HC ??= new Map();
  cvm.ST ??= [];
  cvm.Modify_override ??= async () => {};

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
      await cvm.Modify_override();

      if (zhash(cvm.PTR.buf, cvm.PTR.off)) {
        const prev = cvm.ST.pop();

        if (!prev) return;

        cvm.PTR = prev;
        return cvm.resume();
      }

      const file = await cvm.gethashhashfile(readHash());

      if (isBlockFile(file)) {
        cvm.ST.push({ buf: cvm.PTR.buf, off: cvm.PTR.off });
        cvm.PTR = { buf: file, off: 0 };
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
    cvm.writeU32(b, 0, Number(n) || 0);
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
      : { hash: cvm.hex(x.hash), data: cvm.bytes(x.data ?? new Uint8Array()) };

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

  cvm.parseBlockSafe = (file) => {
    try {
      file = file && file.length ? file : new Uint8Array(32);
      return cvm.parseBlock(file).map(cvm.item);
    } catch {
      return [];
    }
  };

  cvm.readHash = (o = cvm.PTR.off) =>
    cvm.PTR.buf.subarray(o, o + 32);

  cvm.dlen = (o = cvm.PTR.off) =>
    cvm.zhash(cvm.PTR.buf, o) ? 0 : cvm.u32(cvm.PTR.buf, o + 32);

  cvm.data = () =>
    cvm.PTR.buf.subarray(cvm.PTR.off + 36, cvm.PTR.off + 36 + cvm.dlen());

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


CORE_CACHE_JS = r"""
{
  const cvm = CVM;

  cvm.CACHES ??= new Map();

  cvm.cache = (name = "default") => {
    if (!cvm.CACHES.has(name)) cvm.CACHES.set(name, new Map());
    return cvm.CACHES.get(name);
  };

  cvm.memo = async (cacheName, key, loader) => {
    const c = cvm.cache(cacheName);
    if (!c.has(key)) c.set(key, await loader());
    return c.get(key);
  };

  return cvm.resume();
}
"""


EXEC_CALL_JS = r"""
{
  const cvm = CVM;

  cvm.callJS = async (source) =>
    cvm.execute_call(String(source || ""));

  return cvm.resume();
}
"""


def make_net_api_js(base: str) -> str:
    return r"""
{
  const cvm = CVM;
  const configuredBase = __BASE__;

  const pickBase = () => {
    let base = "";

    try {
      if (typeof apiBase !== "undefined" && apiBase) base = apiBase;
    } catch {}

    if (!base && globalThis.apiBase) base = globalThis.apiBase;
    if (!base && cvm.apiBase) base = cvm.apiBase;

    if (
      !base &&
      globalThis.location &&
      (location.protocol === "http:" || location.protocol === "https:") &&
      location.port === "9000"
    ) {
      base = location.origin;
    }

    if (!base) base = configuredBase;

    return String(base).replace(/\/+$/, "");
  };

  cvm.apiBase = pickBase();
  globalThis.apiBase = cvm.apiBase;

  cvm.apiURL = (path) =>
    cvm.apiBase + (String(path).startsWith("/") ? path : "/" + path);

  cvm.apiJSON = async (method, path, data, headers) => {
    const options = { method, headers: headers || {} };
    if (data !== undefined && data !== null) options.body = data;

    const res = await fetch(cvm.apiURL(path), options);
    const json = await res.json();

    if (!json.ok) {
      throw new Error(json.error || `${method} ${path} failed`);
    }

    return json.data;
  };

  cvm.apiUpload = async (data) =>
    cvm.unhex((await cvm.apiJSON("POST", "/api/upload", cvm.bytes(data))).hash);

  cvm.apiChildren = async (parent) =>
    (await cvm.apiJSON("GET", "/api/children/" + cvm.hex(parent))).children || [];

  cvm.apiEdge = async (parent, child) =>
    cvm.apiJSON("POST", "/api/edge/" + cvm.hex(parent) + "/" + cvm.hex(child), new Uint8Array());

  cvm.apiVote = async (user, parent, child) =>
    cvm.apiJSON("POST", "/api/vote/" + cvm.hex(user) + "/" + cvm.hex(parent) + "/" + cvm.hex(child), new Uint8Array());

  cvm.apiUserGet = async (user, keyHash) =>
    cvm.unhex((await cvm.apiJSON("GET", "/api/user/get/" + cvm.hex(user) + "/" + cvm.hex(keyHash))).value);

  cvm.apiUserSet = async (user, keyHash, fileHash) =>
    cvm.apiJSON("POST", "/api/user/set/" + cvm.hex(user) + "/" + cvm.hex(keyHash) + "/" + cvm.hex(fileHash), new Uint8Array());

  cvm.apiDownload = async (hash) => {
    const res = await fetch(cvm.apiURL("/api/file/" + cvm.hex(hash)));
    if (!res.ok) throw new Error("file not found: " + cvm.hex(hash));
    return new Uint8Array(await res.arrayBuffer());
  };

  return cvm.resume();
}
""".replace("__BASE__", json.dumps(base.rstrip("/")))


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

  cvm.Modify_override ??= async () => {};

  cvm.enterBlock = async (block) => {
    block = cvm.bytes(block);
    if (!block.length) block = new Uint8Array(32);

    cvm.ST.push({ buf: cvm.PTR.buf, off: cvm.PTR.off });
    cvm.PTR = { buf: block, off: 0 };

    return cvm.executeBlock();
  };

  cvm.setprog = async (prog) => {
    cvm.PROG = prog.map(cvm.item);
    cvm.ROOT = cvm.buildBlock(cvm.PROG);

    if (cvm.override) {
      cvm.override(await cvm.sha256("HTMLJSstart"), cvm.ROOT);
    }

    return cvm.ROOT;
  };

  cvm.persistRoot = async () => {
    if (!cvm.ROOT) return;

    cvm.PROG = cvm.parseBlock(cvm.ROOT).map(cvm.item);

    if (cvm.override) {
      cvm.override(await cvm.sha256("HTMLJSstart"), cvm.ROOT);
    }

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
        cvm.ST.push({ buf: cvm.PTR.buf, off: cvm.PTR.off });
        cvm.PTR = { buf: file, off: 0 };
        continue;
      }

      return cvm.execute_call(cvm.textDecoder.decode(file));
    }
  };

  return cvm.resume();
}
"""


DOM_CORE_JS = r"""
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

  cvm.toast = (text, ms = 1500) => {
    let el = document.querySelector(".cvm-toast");

    if (!el) {
      el = document.createElement("div");
      el.className = "cvm-toast";
      document.body.appendChild(el);
    }

    el.textContent = text;

    clearTimeout(el.__timer);
    el.__timer = setTimeout(() => el.remove(), ms);
  };

  return cvm.resume();
}
"""


META_OPTIONAL_JS = r"""
{
  const cvm = CVM;

  cvm.META_CACHE ??= new Map();
  cvm.TAG_CACHE ??= new Map();

  cvm.shortHash = (hash) =>
    `${cvm.hex(hash).slice(0, 10)}…`;

  cvm.directText = async (hash) => {
    try {
      const raw = await cvm.downloadCached(hash);
      return cvm.textDecoder.decode(raw).replace(/\s+/g, " ").trim();
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
    return { tag, ...(await cvm.loadMeta(tag)) };
  };

  return cvm.resume();
}
"""


SCHEMA_CORE_JS = r"""
{
  const cvm = CVM;

  cvm.SCHEMA_CACHE ??= new Map();

  cvm.schemaForTag = async (tag) => {
    tag = String(tag || "").trim();

    if (!tag) return null;
    if (cvm.SCHEMA_CACHE.has(tag)) return cvm.SCHEMA_CACHE.get(tag);

    let schema = null;

    try {
      const text = (await cvm.textByName(`${tag}.schema`)).trim();
      if (text) schema = JSON.parse(text);
    } catch {}

    cvm.SCHEMA_CACHE.set(tag, schema);
    return schema;
  };

  const readU32 = (data, off = 0, fallback = 0) =>
    data && data.length >= off + 4 ? cvm.u32(data, off) : fallback;

  cvm.schemaDecode = (schema, data) => {
    data = cvm.bytes(data || new Uint8Array());

    if (!schema) return {};

    if (schema.encode === "u32") {
      const f = schema.fields?.[0]?.name || "value";
      return { [f]: readU32(data, 0, schema.fields?.[0]?.default ?? 0) };
    }

    if (schema.encode === "text") {
      const f = schema.fields?.[0]?.name || "text";
      return { [f]: cvm.textDecoder.decode(data) };
    }

    if (schema.encode === "text-u32") {
      const a = schema.fields?.[0]?.name || "id";
      const b = schema.fields?.[1]?.name || "size";

      if (data.length < 4) return { [a]: "", [b]: schema.fields?.[1]?.default ?? 0 };

      return {
        [a]: cvm.textDecoder.decode(data.slice(0, -4)),
        [b]: readU32(data, data.length - 4, schema.fields?.[1]?.default ?? 0),
      };
    }

    if (schema.encode === "json") {
      try {
        return JSON.parse(cvm.textDecoder.decode(data) || "{}");
      } catch {
        return {};
      }
    }

    return {};
  };

  cvm.schemaEncode = (schema, value) => {
    if (!schema) return new Uint8Array();

    if (schema.encode === "u32") {
      const f = schema.fields?.[0]?.name || "value";
      return cvm.u32bytes(Number(value[f]) || 0);
    }

    if (schema.encode === "text") {
      const f = schema.fields?.[0]?.name || "text";
      return cvm.bytes(value[f] ?? "");
    }

    if (schema.encode === "text-u32") {
      const a = schema.fields?.[0]?.name || "id";
      const b = schema.fields?.[1]?.name || "size";

      return cvm.concat(
        cvm.bytes(value[a] ?? ""),
        cvm.u32bytes(Number(value[b]) || 0)
      );
    }

    if (schema.encode === "json") {
      return cvm.bytes(JSON.stringify(value));
    }

    return new Uint8Array();
  };

  cvm.renderSchemaForm = ({ schema, item, body, commit }) => {
    const value = cvm.schemaDecode(schema, item.data || new Uint8Array());

    body.innerHTML = "";

    for (const field of schema.fields || []) {
      const label = document.createElement("label");
      label.textContent = field.label || field.name;
      body.appendChild(label);

      let input;

      if (field.type === "textarea") {
        input = document.createElement("textarea");
      } else if (field.type === "select") {
        input = document.createElement("select");

        for (const option of field.options || []) {
          const opt = document.createElement("option");
          opt.value = option.value ?? option;
          opt.textContent = option.label ?? option.value ?? option;
          input.appendChild(opt);
        }
      } else if (field.type === "checkbox") {
        input = document.createElement("input");
        input.type = "checkbox";
      } else {
        input = document.createElement("input");
        input.type = field.type || "text";

        if (field.min !== undefined) input.min = field.min;
        if (field.max !== undefined) input.max = field.max;
        if (field.step !== undefined) input.step = field.step;
      }

      if (input.type === "checkbox") {
        input.checked = !!value[field.name];
      } else {
        input.value = value[field.name] ?? field.default ?? "";
      }

      body.appendChild(input);

      const update = () => {
        value[field.name] = input.type === "checkbox"
          ? !!input.checked
          : input.type === "number"
            ? Number(input.value) || 0
            : input.value;

        item.data = cvm.schemaEncode(schema, value);
        commit();
      };

      input.oninput = update;
      input.onchange = update;
    }
  };

  return cvm.resume();
}
"""


MODULESET_STORE_JS = r"""
{
  const cvm = CVM;
  const ZERO_HEX = "00".repeat(32);

  cvm.moduleSet ??= {};

  cvm.moduleSet.ensureUser = () => {
    if (cvm.USER) return cvm.USER;

    const id = prompt("user id");
    if (!id) throw new Error("need user id");

    return cvm.user(id.trim().toLowerCase());
  };

  cvm.moduleSet.keyHash = async (nameOrHash) => {
    const s = String(nameOrHash || "").trim();

    if (/^[0-9a-fA-F]{64}$/.test(s)) {
      return cvm.unhex(s);
    }

    return cvm.sha256(s);
  };

  cvm.moduleSet.load = async (nameOrHash) => {
    const keyHash = await cvm.moduleSet.keyHash(nameOrHash);
    const keyHex = cvm.hex(keyHash);
    const file = await cvm.gethashhashfile(keyHash);

    return {
      keyHash,
      keyHex,
      file,
      items: cvm.parseBlock(file).map(cvm.item),
    };
  };

  cvm.moduleSet.isSet = async (nameOrHash) => {
    try {
      const keyHash = await cvm.moduleSet.keyHash(nameOrHash);
      const file = await cvm.gethashhashfile(keyHash);
      return cvm.isBlockFile(file);
    } catch {
      return false;
    }
  };

  cvm.moduleSet.save = async (nameOrHash, items) => {
    cvm.moduleSet.ensureUser();

    const keyHash = await cvm.moduleSet.keyHash(nameOrHash);
    const file = cvm.buildBlock(items.map(cvm.item));

    cvm.override(keyHash, file);
    await cvm.Modify_override();

    return file;
  };

  cvm.moduleSet.publishNamedFile = async (name, data) => {
    cvm.moduleSet.ensureUser();

    data = cvm.bytes(data);
    await cvm.apiUpload(name);

    const nameHash = await cvm.sha256(name);
    const fileHash = await cvm.apiUpload(data);

    await cvm.apiEdge(nameHash, fileHash);
    await cvm.apiVote(cvm.USER, nameHash, fileHash);

    cvm.HC?.set(cvm.hex(nameHash), fileHash);
    cvm.FC?.set(cvm.hex(fileHash), data);

    return { name, nameHash, fileHash };
  };

  cvm.moduleSet.publishRoot = async (name) => {
    cvm.moduleSet.ensureUser();

    const nameHash = await cvm.sha256(name);

    await cvm.apiEdge(ZERO_HEX, nameHash);
    await cvm.apiVote(cvm.USER, ZERO_HEX, nameHash);

    return nameHash;
  };

  cvm.moduleSet.create = async (name, items = []) => {
    cvm.moduleSet.ensureUser();

    name = String(name || "").trim();

    if (!/^[A-Za-z0-9_.:-]{1,80}$/.test(name)) {
      throw new Error("bad module set name");
    }

    const file = cvm.buildBlock(items.map(cvm.item));
    const out = await cvm.moduleSet.publishNamedFile(name, file);

    await cvm.moduleSet.publishRoot(name);

    return {
      name,
      keyHash: out.nameHash,
      keyHex: cvm.hex(out.nameHash),
      fileHash: out.fileHash,
      items,
    };
  };

  return cvm.resume();
}
"""


EDITOR_BROWSER_JS = r"""
{
  const cvm = CVM;

  cvm.createSimpleBrowser = ({ mount }) => {
    const state = { stack: ["00".repeat(32)] };

    mount.innerHTML = `
      <div class="cvm-browser-head">
        <b>files</b>
        <span></span>
        <button type="button" class="cvm-up">上级</button>
      </div>
      <div class="cvm-browser-path"></div>
      <div class="cvm-browser-list"></div>
    `;

    const pathEl = mount.querySelector(".cvm-browser-path");
    const listEl = mount.querySelector(".cvm-browser-list");

    const render = async () => {
      const current = state.stack.at(-1);

      pathEl.textContent = state.stack.map((x) => x.slice(0, 8)).join("/");
      listEl.innerHTML = "";

      let children = [];
      try { children = await cvm.apiChildren(current); } catch {}

      for (const child of children) {
        const row = document.createElement("div");
        row.className = "cvm-row";
        row.draggable = true;
        row.innerHTML = `
          <span class="cvm-row-name">${child.hash.slice(0, 10)}</span>
          <small>[${child.score}]</small>
        `;

        row.ondragstart = (event) => {
          event.dataTransfer.effectAllowed = "copy";
          event.dataTransfer.setData("text/plain", child.hash);
        };

        row.onclick = () => {
          state.stack.push(child.hash);
          render();
        };

        listEl.appendChild(row);

        (async () => {
          try {
            row.querySelector(".cvm-row-name").textContent = await cvm.tagOf(child.hash);
          } catch {}
        })();
      }
    };

    mount.querySelector(".cvm-up").onclick = () => {
      if (state.stack.length > 1) {
        state.stack.pop();
        render();
      }
    };

    return { state, render };
  };

  return cvm.resume();
}
"""


EDITOR_MODULESETS_JS = r"""
{
  const cvm = CVM;

  if (cvm.__moduleSetEditorCleanFinal) {
    return cvm.resume();
  }

  cvm.__moduleSetEditorCleanFinal = true;

  document.querySelectorAll(".cvm-shell,.cvm2-browser,.cvm2-editor,.cvm2-forge,.cvm8-shell,.cvm9-shell").forEach((el) => el.remove());

  cvm.ensureStyle("cvm-clean-style", `
    .cvm-toast {
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

    .cvm-shell {
      position: fixed;
      inset: 10px;
      z-index: 99999;
      color: #271f1a;
      background: rgba(255,253,248,.98);
      border: 1.4px solid rgba(42,33,28,.82);
      border-radius: 18px;
      box-shadow: 0 18px 70px rgba(30,20,14,.14);
      overflow: hidden;
      font: 13px/1.45 ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
    }

    .cvm-head {
      height: 50px;
      box-sizing: border-box;
      display: flex;
      align-items: center;
      gap: 8px;
      padding: 8px 12px;
      border-bottom: 1px solid rgba(42,33,28,.14);
      user-select: none;
    }

    .cvm-head b {
      font: 950 20px/1 system-ui, sans-serif;
      letter-spacing: -.05em;
    }

    .cvm-head small {
      color: #aaa39d;
      font: 900 10px ui-monospace, monospace;
      letter-spacing: .13em;
      text-transform: uppercase;
    }

    .cvm-spacer { flex: 1; }

    .cvm-head button,
    .cvm-browser button {
      color: #271f1a;
      background: #fff9ee;
      border: 1px solid rgba(42,33,28,.72);
      border-radius: 999px;
      padding: 3px 10px;
      font: 900 11px ui-monospace, monospace;
      cursor: pointer;
    }

    .cvm-body {
      position: absolute;
      inset: 50px 0 0 0;
      display: grid;
      grid-template-columns: 280px 1fr;
      min-height: 0;
    }

    .cvm-browser {
      border-right: 1px solid rgba(42,33,28,.14);
      background: rgba(255,250,241,.72);
      overflow: hidden;
      display: grid;
      grid-template-rows: auto auto 1fr;
    }

    .cvm-browser-head {
      display: grid;
      grid-template-columns: auto 1fr auto;
      align-items: center;
      gap: 8px;
      padding: 9px;
      border-bottom: 1px solid rgba(42,33,28,.1);
    }

    .cvm-browser-head b {
      font: 950 15px/1 system-ui, sans-serif;
      letter-spacing: -.04em;
    }

    .cvm-browser-path {
      padding: 7px 10px;
      color: #8c8580;
      font-size: 11px;
      word-break: break-all;
      border-bottom: 1px solid rgba(42,33,28,.08);
    }

    .cvm-browser-list {
      overflow: auto;
      padding: 8px;
    }

    .cvm-row {
      margin: 6px 0;
      padding: 8px 10px;
      background: rgba(255,255,252,.96);
      border: 1px solid rgba(42,33,28,.24);
      border-radius: 13px;
      cursor: grab;
      overflow: hidden;
      white-space: nowrap;
      text-overflow: ellipsis;
    }

    .cvm-row:hover {
      background: #fff2d8;
      border-color: rgba(42,33,28,.72);
    }

    .cvm-row small,
    .cvm-chip {
      color: #99908a;
      margin-left: 5px;
      font-size: 10px;
      font-weight: 900;
    }

    .cvm-stage {
      position: relative;
      overflow: auto;
      background:
        radial-gradient(circle at 18px 18px, rgba(42,33,28,.17) 1px, transparent 1px),
        linear-gradient(135deg, #fffdf8, #fffaf2);
      background-size: 30px 30px, 100% 100%;
      cursor: default;
    }

    .cvm-stage.middle-panning {
      cursor: grabbing;
      user-select: none;
    }

    .cvm-canvas {
      position: relative;
      width: 9000px;
      height: 6500px;
    }

    .cvm-svg {
      position: absolute;
      left: 0;
      top: 0;
      width: 9000px;
      height: 6500px;
      pointer-events: none;
      overflow: visible;
    }

    .cvm-frames {
      position: absolute;
      left: 0;
      top: 0;
      width: 9000px;
      height: 6500px;
    }

    .cvm-frame {
      position: absolute;
      box-sizing: border-box;
      width: 820px;
      min-width: 520px;
      min-height: 320px;
      background: rgba(255,255,255,.58);
      border: 1.5px solid rgba(42,33,28,.84);
      border-radius: 22px;
      box-shadow: 0 8px 28px rgba(30,20,14,.06);
    }

    .cvm-frame-head {
      position: absolute;
      left: 16px;
      right: 16px;
      top: -38px;
      display: flex;
      align-items: center;
      gap: 8px;
      cursor: move;
      user-select: none;
    }

    .cvm-frame-mark {
      width: 22px;
      height: 22px;
      flex: none;
      border: 4px solid #2a211c;
      border-radius: 50%;
      box-shadow: inset 0 0 0 5px #fffdf8;
      background: #2a211c;
    }

    .cvm-frame-title {
      font: 950 21px/1 system-ui, sans-serif;
      letter-spacing: -.045em;
      white-space: nowrap;
    }

    .cvm-frame-sub {
      color: #aaa39d;
      font: 900 10px ui-monospace, monospace;
      letter-spacing: .13em;
      text-transform: uppercase;
      white-space: nowrap;
    }

    .cvm-frame-body {
      position: absolute;
      left: 16px;
      top: 54px;
      right: 16px;
      bottom: 16px;
      overflow: visible;
    }

    .cvm-frame.drop {
      background: rgba(255,246,225,.84);
      box-shadow: inset 0 0 0 2px rgba(42,33,28,.22);
    }

    .cvm-resize {
      position: absolute;
      right: 8px;
      bottom: 8px;
      width: 18px;
      height: 18px;
      cursor: nwse-resize;
      border-right: 3px solid rgba(42,33,28,.72);
      border-bottom: 3px solid rgba(42,33,28,.72);
      opacity: .72;
    }

    .cvm-node {
      position: absolute;
      box-sizing: border-box;
      width: 260px;
      min-height: 82px;
      padding: 11px 12px;
      color: #271f1a;
      background: rgba(255,255,252,.97);
      border: 1.4px solid rgba(42,33,28,.84);
      border-radius: 17px;
      box-shadow: 0 4px 16px rgba(30,20,14,.08);
      cursor: grab;
      user-select: none;
    }

    .cvm-node:hover { background: #fff7e6; }
    .cvm-node.dragging { cursor: grabbing; opacity: .75; }

    .cvm-node.no-param {
      min-height: 0;
      padding-bottom: 13px;
    }

    .cvm-node.no-param .cvm-data {
      display: none;
    }

    .cvm-node-main {
      display: flex;
      align-items: center;
      gap: 8px;
      min-width: 0;
    }

    .cvm-node-icon {
      display: none;
      width: 25px;
      height: 25px;
      flex: none;
    }

    .cvm-node.has-svg .cvm-node-icon {
      display: grid;
      place-items: center;
    }

    .cvm-node-icon svg {
      width: 25px;
      height: 25px;
      display: block;
    }

    .cvm-node-name {
      min-width: 0;
      overflow: hidden;
      white-space: nowrap;
      text-overflow: ellipsis;
      font: 950 18px/1.05 system-ui, sans-serif;
      letter-spacing: -.04em;
    }

    .cvm-node-desc {
      margin-top: 3px;
      color: #9b948e;
      font-size: 10px;
      font-weight: 900;
      letter-spacing: .08em;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }

    .cvm-data {
      margin-top: 8px;
      padding-top: 7px;
      border-top: 1px solid rgba(42,33,28,.18);
      user-select: text;
      cursor: default;
    }

    .cvm-data label,
    .cvm2-data label {
      display: block;
      margin: 5px 0 3px;
      color: #8c8580;
      font-weight: 900;
      font-size: 10px;
      letter-spacing: .06em;
      text-transform: uppercase;
    }

    .cvm-data input,
    .cvm-data textarea,
    .cvm-data select,
    .cvm2-data input,
    .cvm2-data textarea,
    .cvm2-data select {
      width: 100%;
      box-sizing: border-box;
      color: #271f1a;
      background: #fffaf1;
      border: 1px solid rgba(42,33,28,.58);
      border-radius: 9px;
      padding: 6px;
      font: 12px ui-monospace, monospace;
    }

    .cvm-data textarea {
      height: 52px;
      resize: vertical;
    }

    @media (max-width: 880px) {
      .cvm-body { grid-template-columns: 1fr; }
      .cvm-browser { display: none; }
    }
  `);

  const emptyData = new Uint8Array();
  const BODY_X = 16;
  const BODY_Y = 54;
  const GRID = 10;

  const app = {
    frames: new Map(),
    saveTimers: new Map(),
    layoutTimers: new Map(),
    rendering: false,
  };

  const shell = document.createElement("div");
  shell.className = "cvm-shell";
  shell.innerHTML = `
    <div class="cvm-head">
      <b>module set editor</b>
      <small>VISUAL · LOOP SAFE · DETERMINISTIC</small>
      <span class="cvm-spacer"></span>
      <button type="button" class="cvm-login">登录</button>
    </div>
    <div class="cvm-body">
      <div class="cvm-browser"></div>
      <div class="cvm-stage">
        <div class="cvm-canvas">
          <svg class="cvm-svg" width="9000" height="6500"><g class="cvm-edge-g"></g></svg>
          <div class="cvm-frames"></div>
        </div>
      </div>
    </div>
  `;

  document.body.appendChild(shell);

  const browserEl = shell.querySelector(".cvm-browser");
  const stage = shell.querySelector(".cvm-stage");
  const framesEl = shell.querySelector(".cvm-frames");
  const edgeG = shell.querySelector(".cvm-edge-g");

  const snap = (n) => Math.round(n / GRID) * GRID;

  const worldPoint = (event) => {
    const r = stage.getBoundingClientRect();

    return {
      x: event.clientX - r.left + stage.scrollLeft,
      y: event.clientY - r.top + stage.scrollTop,
    };
  };

  const layoutNS = () => `CVM.clean.layout.${cvm.USER || "public"}`;
  const layoutKey = (id) => `${layoutNS()}.${id}`;

  const loadLayout = (id) => {
    try {
      const out = JSON.parse(localStorage.getItem(layoutKey(id)) || "{}");
      out.nodes ??= {};
      out.frame ??= {};
      return out;
    } catch {
      return { nodes: {}, frame: {} };
    }
  };

  const saveLayoutNow = (frame) => {
    const layout = frame.layout || loadLayout(frame.id);

    layout.nodes ??= {};
    layout.frame ??= {};

    layout.frame = {
      ...layout.frame,
      x: frame.x,
      y: frame.y,
      w: frame.w,
      h: frame.h,
      manualSize: !!frame.manualSize,
    };

    try {
      localStorage.setItem(layoutKey(frame.id), JSON.stringify(layout));
    } catch {}
  };

  const queueLayoutSave = (frame) => {
    clearTimeout(app.layoutTimers.get(frame.id));
    app.layoutTimers.set(frame.id, setTimeout(() => saveLayoutNow(frame), 180));
  };

  const itemKey = (index, item) => `${index}:${item.hash}`;

  const defaultNodePos = (index) => ({
    x: 48 + (index % 3) * 300,
    y: 52 + Math.floor(index / 3) * 180,
  });

  const ensureFrameLayout = (frame) => {
    const layout = loadLayout(frame.id);
    frame.layout = layout;

    if (layout.frame) {
      frame.x = layout.frame.x ?? frame.x;
      frame.y = layout.frame.y ?? frame.y;
      frame.w = layout.frame.w ?? frame.w;
      frame.h = layout.frame.h ?? frame.h;
      frame.manualSize = !!layout.frame.manualSize;
    }

    return layout;
  };

  const findFrameEl = (id) =>
    [...framesEl.querySelectorAll(".cvm-frame")].find((el) => el.__frameId === id);

  const findNodeEl = (frameId, index) =>
    [...framesEl.querySelectorAll(".cvm-node")].find((el) => el.__frameId === frameId && el.__index === index);

  const scheduleSave = (frame) => {
    clearTimeout(app.saveTimers.get(frame.id));

    app.saveTimers.set(frame.id, setTimeout(async () => {
      try {
        await cvm.moduleSet.save(frame.keyHex, frame.items);
        cvm.toast("saved", 850);
      } catch (err) {
        console.warn("save module set failed", err);
        cvm.toast("save failed: " + (err.message || err), 2400);
      }
    }, 420));
  };

  const nodeCenterWorld = (frame, index) => {
    const el = findNodeEl(frame.id, index);
    if (!el) return null;

    const x = parseFloat(el.style.left) || 0;
    const y = parseFloat(el.style.top) || 0;

    return {
      x: frame.x + BODY_X + x + el.offsetWidth / 2,
      y: frame.y + BODY_Y + y + el.offsetHeight / 2,
    };
  };

  const drawPath = (a, b, dashed = false) => {
    const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
    const mid = Math.max(40, Math.abs(b.x - a.x) / 2);

    path.setAttribute("d", `M ${a.x} ${a.y} C ${a.x + mid} ${a.y}, ${b.x - mid} ${b.y}, ${b.x} ${b.y}`);
    path.setAttribute("fill", "none");
    path.setAttribute("stroke", "#2a211c");
    path.setAttribute("stroke-width", dashed ? "1" : "1.45");
    path.setAttribute("opacity", dashed ? ".32" : ".72");

    if (dashed) path.setAttribute("stroke-dasharray", "7 6");

    edgeG.appendChild(path);
  };

  const redrawEdges = () => {
    edgeG.innerHTML = "";

    for (const frame of app.frames.values()) {
      for (let i = 1; i < frame.items.length; i++) {
        const a = nodeCenterWorld(frame, i - 1);
        const b = nodeCenterWorld(frame, i);
        if (a && b) drawPath(a, b, false);
      }

      if (frame.parent) {
        const parent = app.frames.get(frame.parent.frameId);
        const a = parent && nodeCenterWorld(parent, frame.parent.index);
        const b = { x: frame.x + 24, y: frame.y - 24 };
        if (a) drawPath(a, b, true);
      }
    }
  };

  const fitFrame = (frame) => {
    const el = findFrameEl(frame.id);
    if (!el) return;

    const baseW = frame.root ? 820 : 760;
    const baseH = frame.root ? 520 : 430;

    let w = baseW;
    let h = baseH;

    for (const node of el.querySelectorAll(".cvm-node")) {
      const x = parseFloat(node.style.left) || 0;
      const y = parseFloat(node.style.top) || 0;

      w = Math.max(w, BODY_X + x + node.offsetWidth + 58);
      h = Math.max(h, BODY_Y + y + node.offsetHeight + 56);
    }

    frame.w = Math.max(520, frame.manualSize ? frame.w || w : w, w);
    frame.h = Math.max(320, frame.manualSize ? frame.h || h : h, h);

    el.style.width = `${frame.w}px`;
    el.style.height = `${frame.h}px`;

    queueLayoutSave(frame);
  };

  const separateFrames = () => {
    const xs = [...app.frames.values()];

    for (let pass = 0; pass < 8; pass++) {
      let moved = false;

      for (let i = 0; i < xs.length; i++) {
        for (let j = i + 1; j < xs.length; j++) {
          const a = xs[i];
          const b = xs[j];

          const overlap =
            a.x < b.x + b.w + 70 &&
            a.x + a.w + 70 > b.x &&
            a.y < b.y + b.h + 60 &&
            a.y + a.h + 60 > b.y;

          if (!overlap) continue;

          b.x = snap(a.x + a.w + 110);
          b.y = snap(Math.max(90, b.y + 40));

          const el = findFrameEl(b.id);
          if (el) {
            el.style.left = `${b.x}px`;
            el.style.top = `${b.y}px`;
          }

          saveLayoutNow(b);
          moved = true;
        }
      }

      if (!moved) break;
    }
  };

  const frameLocalFromEvent = (frame, event) => {
    const p = worldPoint(event);

    return {
      x: p.x - frame.x - BODY_X,
      y: p.y - frame.y - BODY_Y,
    };
  };

  const loadRoot = async () => {
    const root = await cvm.moduleSet.load("HTMLJSstart");

    app.frames.clear();

    app.frames.set("root", {
      id: "root",
      keyHex: root.keyHex,
      title: "HTMLJSstart",
      subtitle: "VM FIRST RUN MODULE SET",
      items: root.items,
      x: 100,
      y: 130,
      w: 820,
      h: 520,
      root: true,
    });
  };

  const saveItemData = (frame, index, item) => {
    frame.items[index] = cvm.item(item);
    scheduleSave(frame);
    redrawEdges();
  };

  const renderData = async (frame, index, item, node, meta) => {
    const body = node.querySelector(".cvm-data");
    body.innerHTML = "";

    let schema = null;

    try { schema = await cvm.schemaForTag(meta.tag); } catch {}

    if (schema) {
      node.classList.remove("no-param");

      cvm.renderSchemaForm({
        schema,
        item,
        body,
        commit: () => saveItemData(frame, index, item),
      });

      fitFrame(frame);
      redrawEdges();
      return;
    }

    const source = String(meta.metersupport || "").trim();

    if (!source || source.includes("没有节点参数 data")) {
      node.classList.add("no-param");
      body.innerHTML = "";
      fitFrame(frame);
      redrawEdges();
      return;
    }

    node.classList.remove("no-param");

    try {
      const fn = eval(`(${source})`);

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
          commit: () => saveItemData(frame, index, item),
        },
      });
    } catch (err) {
      console.warn("metersupport failed", meta.tag, err);
      body.innerHTML = `<div style="color:#b33;font-weight:900">metersupport failed</div>`;
    }

    fitFrame(frame);
    redrawEdges();
  };

  const hydrateNode = async (frame, index, item, node) => {
    let meta = {
      tag: item.hash.slice(0, 10),
      describe: "",
      svg: "",
      metersupport: "",
    };

    try { meta = await cvm.metaForHash(item.hash); } catch {}

    if (!node.isConnected || node.__frameId !== frame.id || node.__index !== index) return;

    const icon = node.querySelector(".cvm-node-icon");
    const name = node.querySelector(".cvm-node-name");
    const desc = node.querySelector(".cvm-node-desc-text");

    name.textContent = meta.tag || item.hash.slice(0, 10);
    desc.textContent = meta.describe || "module";

    if (meta.svg) {
      icon.innerHTML = meta.svg;
      node.classList.add("has-svg");
    } else {
      icon.innerHTML = "";
      node.classList.remove("has-svg");
    }

    await renderData(frame, index, item, node, meta);
  };

  const dragAbs = (el, get, set, onEnd) => {
    let drag = null;

    el.onmousedown = (event) => {
      if (event.button !== 0) return;
      if (event.target.closest("input,textarea,select,button")) return;

      const p = get();

      drag = {
        sx: event.clientX,
        sy: event.clientY,
        px: p.x,
        py: p.y,
        moved: false,
      };

      el.classList.add("dragging");
      event.preventDefault();
      event.stopPropagation();

      const move = (event) => {
        const dx = event.clientX - drag.sx;
        const dy = event.clientY - drag.sy;

        if (Math.hypot(dx, dy) > 4) drag.moved = true;

        set({
          x: Math.max(12, drag.px + dx),
          y: Math.max(12, drag.py + dy),
        });
      };

      const up = async () => {
        removeEventListener("mousemove", move);
        removeEventListener("mouseup", up);

        el.classList.remove("dragging");

        if (drag?.moved) await onEnd?.();

        drag = null;
      };

      addEventListener("mousemove", move);
      addEventListener("mouseup", up);
    };
  };

  const maybeConnect = async (frame, draggedIndex) => {
    if (draggedIndex < 0 || draggedIndex >= frame.items.length) return false;

    const draggedEl = findNodeEl(frame.id, draggedIndex);
    if (!draggedEl) return false;

    const dx = parseFloat(draggedEl.style.left) || 0;
    const dy = parseFloat(draggedEl.style.top) || 0;

    const dc = {
      x: dx + draggedEl.offsetWidth / 2,
      y: dy + draggedEl.offsetHeight / 2,
    };

    let best = null;

    for (let i = 0; i < frame.items.length; i++) {
      if (i === draggedIndex) continue;

      const el = findNodeEl(frame.id, i);
      if (!el) continue;

      const x = parseFloat(el.style.left) || 0;
      const y = parseFloat(el.style.top) || 0;

      const c = {
        x: x + el.offsetWidth / 2,
        y: y + el.offsetHeight / 2,
      };

      const dist = Math.hypot(dc.x - c.x, dc.y - c.y);
      const gap = Math.max(0, dist - (draggedEl.offsetWidth + el.offsetWidth) / 2);

      if (!best || gap < best.gap) {
        best = { index: i, gap, center: c };
      }
    }

    if (!best || best.gap > 58) return false;

    const layout = frame.layout;

    const snapshot = frame.items.map((item, index) => ({
      item,
      pos: { ...(layout.nodes[itemKey(index, item)] || defaultNodePos(index)) },
    }));

    const moved = frame.items.splice(draggedIndex, 1)[0];

    let target = best.index;
    if (draggedIndex < target) target--;

    const after =
      dc.x > best.center.x ||
      (Math.abs(dc.x - best.center.x) < 80 && dc.y > best.center.y);

    const insert = Math.max(0, Math.min(frame.items.length, target + (after ? 1 : 0)));
    frame.items.splice(insert, 0, moved);

    layout.nodes = {};

    for (let i = 0; i < frame.items.length; i++) {
      const item = frame.items[i];
      const old = snapshot.find((x) => x.item === item);
      layout.nodes[itemKey(i, item)] = old ? old.pos : defaultNodePos(i);
    }

    saveLayoutNow(frame);
    scheduleSave(frame);

    await renderEditor();
    return true;
  };

  const openFrame = async (keyHash, options = {}) => {
    const keyHex = cvm.hex(keyHash);
    const id = `set:${keyHex}`;

    if (app.frames.has(id)) {
      cvm.toast("模块集已经展开", 900);
      return;
    }

    const loaded = await cvm.moduleSet.load(keyHex);

    const frame = {
      id,
      keyHex,
      title: options.title || await cvm.tagOf(keyHex),
      subtitle: "EXPANDED MODULE SET",
      items: loaded.items,
      x: options.x ?? 980,
      y: options.y ?? 150,
      w: 760,
      h: 430,
      parent: options.parent,
      root: false,
    };

    app.frames.set(id, frame);
    await renderEditor();
  };

  const suggestSetName = (frame) => {
    const base = String(frame.title || "set")
      .replace(/[^A-Za-z0-9_.:-]+/g, ".")
      .replace(/^\.+|\.+$/g, "")
      .slice(0, 32) || "set";

    return `${base}.${frame.items.length + 1}.bin`;
  };

  const createSetInside = async (frame, point) => {
    const name = prompt("模块集名称", suggestSetName(frame));
    if (!name) return;

    try {
      const created = await cvm.moduleSet.create(name.trim(), []);

      const item = {
        hash: cvm.hex(created.keyHash),
        data: emptyData,
      };

      const index = frame.items.length;
      frame.items.push(item);

      frame.layout.nodes[itemKey(index, item)] = {
        x: snap(Math.max(12, point.x - 130)),
        y: snap(Math.max(12, point.y - 50)),
      };

      saveLayoutNow(frame);
      scheduleSave(frame);

      await browser.render();
      await renderEditor();

      cvm.toast(`created ${created.name}`, 1500);

      setTimeout(() => {
        findNodeEl(frame.id, index)?.dispatchEvent(new MouseEvent("dblclick", { bubbles: true }));
      }, 120);
    } catch (err) {
      console.warn("create module set failed", err);
      cvm.toast("create failed: " + (err.message || err), 2400);
    }
  };

  const renderFrame = async (frame) => {
    ensureFrameLayout(frame);

    const el = document.createElement("div");
    el.className = "cvm-frame";
    el.__frameId = frame.id;
    el.style.left = `${frame.x}px`;
    el.style.top = `${frame.y}px`;
    el.style.width = `${frame.w || 760}px`;
    el.style.height = `${frame.h || 430}px`;

    el.innerHTML = `
      <div class="cvm-frame-head" title="${frame.root ? "拖动模块集" : "拖动模块集，双击关闭"}">
        <span class="cvm-frame-mark"></span>
        <span class="cvm-frame-title">${cvm.esc(frame.title)}</span>
        <span class="cvm-frame-sub">${cvm.esc(frame.subtitle || "MODULE SET")}</span>
      </div>
      <div class="cvm-frame-body"></div>
      <div class="cvm-resize" title="拖拽调整大小，双击恢复自动"></div>
    `;

    framesEl.appendChild(el);

    const head = el.querySelector(".cvm-frame-head");
    const body = el.querySelector(".cvm-frame-body");
    const resize = el.querySelector(".cvm-resize");

    dragAbs(
      head,
      () => ({ x: frame.x, y: frame.y }),
      (p) => {
        frame.x = snap(p.x);
        frame.y = snap(p.y);

        el.style.left = `${frame.x}px`;
        el.style.top = `${frame.y}px`;

        queueLayoutSave(frame);
        redrawEdges();
      },
      async () => {
        separateFrames();
        redrawEdges();
      }
    );

    head.ondblclick = () => {
      if (frame.root) return;
      app.frames.delete(frame.id);
      renderEditor();
    };

    resize.onmousedown = (event) => {
      if (event.button !== 0) return;

      const start = {
        x: event.clientX,
        y: event.clientY,
        w: el.offsetWidth,
        h: el.offsetHeight,
      };

      frame.manualSize = true;

      event.preventDefault();
      event.stopPropagation();

      const move = (event) => {
        frame.w = snap(Math.max(520, start.w + event.clientX - start.x));
        frame.h = snap(Math.max(320, start.h + event.clientY - start.y));

        el.style.width = `${frame.w}px`;
        el.style.height = `${frame.h}px`;

        queueLayoutSave(frame);
        redrawEdges();
      };

      const up = () => {
        removeEventListener("mousemove", move);
        removeEventListener("mouseup", up);
      };

      addEventListener("mousemove", move);
      addEventListener("mouseup", up);
    };

    resize.ondblclick = (event) => {
      event.preventDefault();
      event.stopPropagation();

      frame.manualSize = false;
      fitFrame(frame);
      redrawEdges();
    };

    body.ondragover = (event) => {
      event.preventDefault();
      el.classList.add("drop");
    };

    body.ondragleave = (event) => {
      if (!el.contains(event.relatedTarget)) el.classList.remove("drop");
    };

    body.ondrop = async (event) => {
      event.preventDefault();
      el.classList.remove("drop");

      const hash = event.dataTransfer.getData("text/plain");
      if (!hash) return;

      const p = frameLocalFromEvent(frame, event);
      const item = { hash, data: emptyData };
      const index = frame.items.length;

      frame.items.push(item);

      frame.layout.nodes[itemKey(index, item)] = {
        x: snap(Math.max(12, p.x - 130)),
        y: snap(Math.max(12, p.y - 50)),
      };

      saveLayoutNow(frame);
      scheduleSave(frame);

      await renderEditor();
    };

    body.ondblclick = async (event) => {
      if (event.target.closest(".cvm-node,input,textarea,select,button")) return;

      event.preventDefault();
      event.stopPropagation();

      await createSetInside(frame, frameLocalFromEvent(frame, event));
    };

    for (let index = 0; index < frame.items.length; index++) {
      const item = cvm.item(frame.items[index]);
      frame.items[index] = item;

      const k = itemKey(index, item);
      const pos = frame.layout.nodes[k] || defaultNodePos(index);
      frame.layout.nodes[k] = pos;

      const node = document.createElement("div");
      node.className = "cvm-node no-param";
      node.__frameId = frame.id;
      node.__index = index;
      node.style.left = `${pos.x}px`;
      node.style.top = `${pos.y}px`;
      node.title = "双击模块集节点可展开";

      node.innerHTML = `
        <div class="cvm-node-main">
          <div class="cvm-node-icon"></div>
          <div class="cvm-node-name">${cvm.esc(item.hash.slice(0, 10))}</div>
        </div>
        <div class="cvm-node-desc">
          <span class="cvm-node-desc-text">loading</span>
          <span class="cvm-chip">${item.hash.slice(0, 8)}</span>
        </div>
        <div class="cvm-data cvm2-data"></div>
      `;

      body.appendChild(node);

      dragAbs(
        node,
        () => frame.layout.nodes[k],
        (p) => {
          frame.layout.nodes[k] = {
            x: Math.max(12, p.x),
            y: Math.max(12, p.y),
          };

          node.style.left = `${frame.layout.nodes[k].x}px`;
          node.style.top = `${frame.layout.nodes[k].y}px`;

          fitFrame(frame);
          redrawEdges();
          queueLayoutSave(frame);
        },
        async () => {
          frame.layout.nodes[k].x = snap(frame.layout.nodes[k].x);
          frame.layout.nodes[k].y = snap(frame.layout.nodes[k].y);

          node.style.left = `${frame.layout.nodes[k].x}px`;
          node.style.top = `${frame.layout.nodes[k].y}px`;

          const connected = await maybeConnect(frame, index);

          if (!connected) {
            saveLayoutNow(frame);
            scheduleSave(frame);
            redrawEdges();
          }
        }
      );

      node.ondblclick = async (event) => {
        if (event.target.closest("input,textarea,select,button")) return;

        event.preventDefault();
        event.stopPropagation();

        let isSet = false;
        try { isSet = await cvm.moduleSet.isSet(item.hash); } catch {}

        if (!isSet) return;

        const title = node.querySelector(".cvm-node-name")?.textContent || await cvm.tagOf(item.hash);

        await openFrame(item.hash, {
          title,
          parent: { frameId: frame.id, index },
          x: snap(frame.x + (frame.w || 760) + 110),
          y: snap(frame.y + 90 + index * 36),
        });
      };

      hydrateNode(frame, index, item, node);
    }

    fitFrame(frame);
  };

  async function renderEditor() {
    if (app.rendering) return;

    app.rendering = true;

    try {
      framesEl.innerHTML = "";
      edgeG.innerHTML = "";

      for (const frame of app.frames.values()) {
        await renderFrame(frame);
      }

      separateFrames();
      redrawEdges();
    } finally {
      app.rendering = false;
    }
  }

  const browser = cvm.createSimpleBrowser({ mount: browserEl });

  shell.querySelector(".cvm-login").onclick = async () => {
    const id = prompt("user id");
    if (!id) return;

    cvm.user(id.trim().toLowerCase());

    await loadRoot();
    await browser.render();
    await renderEditor();

    cvm.toast("user loaded", 1000);
  };

  let pan = null;

  stage.addEventListener("mousedown", (event) => {
    if (event.button !== 1) return;

    pan = {
      x: event.clientX,
      y: event.clientY,
      left: stage.scrollLeft,
      top: stage.scrollTop,
    };

    stage.classList.add("middle-panning");

    event.preventDefault();
    event.stopPropagation();
  });

  addEventListener("mousemove", (event) => {
    if (!pan) return;

    stage.scrollLeft = pan.left - (event.clientX - pan.x);
    stage.scrollTop = pan.top - (event.clientY - pan.y);
  });

  addEventListener("mouseup", () => {
    pan = null;
    stage.classList.remove("middle-panning");
  });

  stage.addEventListener("auxclick", (event) => {
    if (event.button === 1) event.preventDefault();
  });

  stage.ondblclick = async (event) => {
    if (event.target.closest(".cvm-frame,.cvm-node,input,textarea,select,button")) return;

    const root = app.frames.get("root");
    if (!root) return;

    event.preventDefault();

    const p = worldPoint(event);

    await createSetInside(root, {
      x: p.x - root.x - BODY_X,
      y: p.y - root.y - BODY_Y,
    });
  };

  cvm.moduleSetEditorClean = {
    app,
    renderEditor,
    loadRoot,
    openFrame,
  };

  await loadRoot();
  await browser.render();
  await renderEditor();

  return cvm.resume();
}
"""


FLOW_DELAY_JS = r"""
{
  const cvm = CVM;
  const d = cvm.data();
  const ms = d.length >= 4 ? cvm.u32(d, 0) : 1000;
  await cvm.sleep(ms);
  return cvm.resume();
}
"""


MODULES_JS = {
    "rerun": "CVM.PTR.off=0;return CVM.executeBlock();\n",

    "print": r"""
{
  const cvm = CVM;
  const d = cvm.data ? cvm.data() : new Uint8Array();
  const text = d.length ? cvm.textDecoder.decode(d) : "hello world";

  let output = document.getElementById("cvm-out");

  if (!output) {
    output = document.createElement("div");
    output.id = "cvm-out";
    output.style.cssText = "position:fixed;left:50%;top:14px;z-index:99998;transform:translateX(-50%);padding:6px 18px;color:#271f1a;background:#fff3ce;border:1px solid rgba(42,33,28,.75);border-radius:999px;font:900 28px system-ui,sans-serif";
    document.body.appendChild(output);
  }

  output.textContent = text;
  return cvm.resume();
}
""",

    "setsize": r"""
{
  const cvm = CVM;
  const d = cvm.data();

  if (d.length >= 4) {
    const id = d.slice(0, d.length - 4);
    const size = cvm.u32(d, d.length - 4);
    cvm.setVarSize(id, size);
  }

  return cvm.resume();
}
""",

    "getvar": r"""
{
  const cvm = CVM;
  const id = cvm.data();
  cvm.stdReturn(cvm.getVar(id));
  return cvm.resume();
}
""",

    "setvar": r"""
{
  const cvm = CVM;
  const id = cvm.data();
  const size = cvm.VSZ.get(cvm.varKey(id)) ?? 0;

  cvm.stdInput();
  cvm.setVar(id, cvm.stdRead(size));

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


def schema(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=2)


SCHEMAS = {
    "cvm.flow.delay.schema": schema({
        "title": "delay",
        "encode": "u32",
        "fields": [
            {"name": "ms", "type": "number", "label": "延迟毫秒", "default": 1000, "min": 0, "step": 1}
        ],
    }),

    "print.schema": schema({
        "title": "print",
        "encode": "text",
        "fields": [
            {"name": "text", "type": "textarea", "label": "输出文本", "default": "hello world"}
        ],
    }),

    "getvar.schema": schema({
        "title": "getvar",
        "encode": "text",
        "fields": [
            {"name": "id", "type": "text", "label": "变量 ID", "default": ""}
        ],
    }),

    "setvar.schema": schema({
        "title": "setvar",
        "encode": "text",
        "fields": [
            {"name": "id", "type": "text", "label": "变量 ID", "default": ""}
        ],
    }),

    "setsize.schema": schema({
        "title": "setsize",
        "encode": "text-u32",
        "fields": [
            {"name": "id", "type": "text", "label": "变量 ID", "default": ""},
            {"name": "size", "type": "number", "label": "变量大小", "default": 0, "min": 0, "step": 1},
        ],
    }),
}


BOOT_SETS = {
    "cvm.boot.core.bin": [
        "cvm.core.codec",
        "cvm.core.block",
        "cvm.core.memory",
        "cvm.core.cache",
        "cvm.exec.call",
    ],

    "cvm.boot.net.bin": [
        "cvm.net.api",
        "cvm.store.named",
    ],

    "cvm.boot.exec.bin": [
        "cvm.exec.block",
    ],

    "cvm.boot.ui.bin": [
        "cvm.dom.core",
    ],

    "cvm.boot.meta.bin": [
        "cvm.meta.optional",
    ],

    "cvm.boot.schema.bin": [
        "cvm.schema.core",
    ],

    "cvm.boot.moduleSet.bin": [
        "cvm.moduleSet.store",
    ],

    "cvm.boot.editor.bin": [
        "cvm.editor.browser",
        "cvm.editor.moduleSets",
    ],
}


def svg_for(name: str) -> str:
    text = name[:4]
    return f"""<svg viewBox="0 0 64 64" xmlns="http://www.w3.org/2000/svg">
  <rect x="8" y="8" width="48" height="48" rx="8" fill="#fffaf1" stroke="#2a211c" stroke-width="4"/>
  <text x="32" y="40" font-size="18" fill="#2a211c" text-anchor="middle" font-family="monospace" font-weight="900">{text}</text>
</svg>"""


def build_files(base: str):
    files = {
        "start.loader": LOADER_JS,
        "start": LOADER_JS,

        "cvm.core.codec": CORE_CODEC_JS,
        "cvm.core.block": CORE_BLOCK_JS,
        "cvm.core.memory": CORE_MEMORY_JS,
        "cvm.core.cache": CORE_CACHE_JS,
        "cvm.exec.call": EXEC_CALL_JS,
        "cvm.net.api": make_net_api_js(base),
        "cvm.store.named": STORE_NAMED_JS,
        "cvm.exec.block": EXEC_BLOCK_JS,
        "cvm.dom.core": DOM_CORE_JS,
        "cvm.meta.optional": META_OPTIONAL_JS,
        "cvm.schema.core": SCHEMA_CORE_JS,
        "cvm.moduleSet.store": MODULESET_STORE_JS,
        "cvm.editor.browser": EDITOR_BROWSER_JS,
        "cvm.editor.moduleSets": EDITOR_MODULESETS_JS,
        "cvm.flow.delay": FLOW_DELAY_JS,
    }

    files.update(MODULES_JS)
    files.update(SCHEMAS)

    for name, items in BOOT_SETS.items():
        files[name] = block(items)

    files["start.bin"] = block([
        "cvm.boot.core.bin",
        "cvm.boot.net.bin",
        "cvm.boot.exec.bin",
        "cvm.boot.ui.bin",
        "cvm.boot.meta.bin",
        "cvm.boot.schema.bin",
        "cvm.boot.moduleSet.bin",
        "cvm.boot.editor.bin",
    ])

    # 循环保留：启动 -> 编辑器 -> 延迟 -> rerun。
    files["HTMLJSstart"] = block([
        "start.loader",
        "start.bin",
        ("cvm.flow.delay", le32(1000)),
        "rerun",
    ])

    files["base.bin"] = block([
        "print",
        "setsize",
        "getvar",
        "setvar",
        "IF",
        "IFrerun",
        "Runonce",
    ])

    describes = {
        "HTMLJSstart.describe": "VM 入口。保留循环：start.loader -> start.bin -> delay -> rerun。",
        "start.loader.describe": "最小启动器，负责进入 block/JS 混合执行。",
        "start.bin.describe": "启动模块集：按 core/net/exec/ui/meta/schema/moduleSet/editor 能力层拆分。",
        "base.bin.describe": "基础逻辑模块集。",

        "cvm.boot.core.bin.describe": "boot core：编码、block、内存、缓存、JS 调用。",
        "cvm.boot.net.bin.describe": "boot net：HTTP API 与命名存储。",
        "cvm.boot.exec.bin.describe": "boot exec：block 执行器。",
        "cvm.boot.ui.bin.describe": "boot ui：极简 DOM/UI 工具。",
        "cvm.boot.meta.bin.describe": "boot meta：tag、svg、describe、metersupport。",
        "cvm.boot.schema.bin.describe": "boot schema：高级参数 schema。",
        "cvm.boot.moduleSet.bin.describe": "boot moduleSet：模块集加载、保存、创建、发布。",
        "cvm.boot.editor.bin.describe": "boot editor：文件浏览器与可视化模块集编辑器。",

        "cvm.core.codec.describe": "通用编码：bytes、hex、u32、concat、sleep。",
        "cvm.core.block.describe": "模块集 block 编解码。",
        "cvm.core.memory.describe": "std 缓冲与变量内存。",
        "cvm.core.cache.describe": "通用缓存 cache / memo。",
        "cvm.exec.call.describe": "JS 调用薄封装。",
        "cvm.net.api.describe": "HTTP API 封装。",
        "cvm.store.named.describe": "命名文件解析、缓存、用户覆盖。",
        "cvm.exec.block.describe": "安全 block 执行器。",
        "cvm.dom.core.describe": "极简 DOM 工具：esc、ensureStyle、toast。",
        "cvm.meta.optional.describe": "可选元数据：tag、svg、describe、metersupport。",
        "cvm.schema.core.describe": "schema 参数系统：优先自动生成可视化参数 UI。",
        "cvm.moduleSet.store.describe": "模块集存储与创建能力。",
        "cvm.editor.browser.describe": "轻量文件浏览器。",
        "cvm.editor.moduleSets.describe": "可视化模块集编辑器：确定性、循环安全、可视化优先。",
        "cvm.flow.delay.describe": "等待 data 中 uint32 毫秒后继续执行。",

        "rerun.describe": "把当前 block 指针归零并重新执行，用于循环。",
        "print.describe": "输出 data 文本。",
        "setsize.describe": "data: 变量 ID + uint32 size。",
        "getvar.describe": "data: 变量 ID。读取变量到 std。",
        "setvar.describe": "data: 变量 ID。从 std 写变量。",
        "IF.describe": "data: 内部模块集。std bool 为 true 时执行。",
        "IFrerun.describe": "std bool 为 true 时重新执行当前模块集。",
        "Runonce.describe": "data: enabled byte + 内部模块集，只执行一次。",
    }

    files.update(describes)

    svg_names = [
        "HTMLJSstart",
        "start.loader",
        "start",
        "start.bin",
        "base.bin",
        *BOOT_SETS.keys(),
        "cvm.core.codec",
        "cvm.core.block",
        "cvm.core.memory",
        "cvm.core.cache",
        "cvm.exec.call",
        "cvm.net.api",
        "cvm.store.named",
        "cvm.exec.block",
        "cvm.dom.core",
        "cvm.meta.optional",
        "cvm.schema.core",
        "cvm.moduleSet.store",
        "cvm.editor.browser",
        "cvm.editor.moduleSets",
        "cvm.flow.delay",
        "rerun",
        "print",
        "setsize",
        "getvar",
        "setvar",
        "IF",
        "IFrerun",
        "Runonce",
    ]

    for name in svg_names:
        files[f"{name}.svg"] = svg_for(name)

    out = {}

    for name, data in files.items():
        if isinstance(data, bytes):
            out[name] = data
        else:
            out[name] = str(data).encode("utf-8")

    return out


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default=BASE_DEFAULT)
    parser.add_argument("--id", default="id.bin")
    parser.add_argument("--write-index", default="", help="可选：写出 index.html")
    args = parser.parse_args()

    api = API(args.base)
    user = get_or_create_id(api, args.id)

    print(f"\n服务器: {args.base}")
    print(f"用户ID: {user}\n")

    if args.write_index:
        Path(args.write_index).write_text(make_index_html(args.base), encoding="utf-8")
        print(f"[+] wrote index: {args.write_index}")

    files = build_files(args.base)

    print("\n上传文件...")
    for name, data in files.items():
        put(api, user, name, data)

    root_items = [
        "HTMLJSstart",
        "start.loader",
        "start",
        "start.bin",
        "base.bin",
        *BOOT_SETS.keys(),

        "cvm.core.codec",
        "cvm.core.block",
        "cvm.core.memory",
        "cvm.core.cache",
        "cvm.exec.call",
        "cvm.net.api",
        "cvm.store.named",
        "cvm.exec.block",
        "cvm.dom.core",
        "cvm.meta.optional",
        "cvm.schema.core",
        "cvm.moduleSet.store",
        "cvm.editor.browser",
        "cvm.editor.moduleSets",
        "cvm.flow.delay",

        "rerun",
        "print",
        "setsize",
        "getvar",
        "setvar",
        "IF",
        "IFrerun",
        "Runonce",
    ]

    print("\n挂载根目录...")
    for name in root_items:
        mount_root(api, user, name)

    print("\n✅ CVM clean 完整部署完成")
    print("入口：HTMLJSstart -> start.loader -> start.bin -> delay -> rerun")
    print("start.bin 已拆分为 boot.core/net/exec/ui/meta/schema/moduleSet/editor")
    print("编辑器：确定性、循环安全、可视化优先、schema 优先、无参数则不显示 data 区")
    print("浏览器请 Ctrl+F5 强制刷新；如果浏览器自身缩放过，请 Ctrl+0。")


if __name__ == "__main__":
    main()
