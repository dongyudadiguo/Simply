#!/usr/bin/env python3
import argparse
import hashlib
import json
import struct
import sys
import urllib.error
import urllib.request


API_DEFAULT = "http://124.221.146.23:9000"


START_JS = r"""
(async () => {
  const cvm = CVM;
  const enc = new TextEncoder();
  const dec = new TextDecoder();

  const hex = (x) => typeof x === "string" ? x : cvm.hex(x);
  const unhex = (h) => new Uint8Array(h.match(/../g).map((x) => parseInt(x, 16)));

  const short = (h) => h.slice(0, 8) + "..." + h.slice(-6);

  const apiJSON = async (url, options = {}) => {
    const res = await fetch(url, options);
    const json = await res.json();

    if (!json.ok) {
      throw new Error(json.error || "api failed");
    }

    return json.data;
  };

  const read32 = () =>
    new DataView(cvm.PTR.buf.buffer, cvm.PTR.buf.byteOffset)
      .getUint32(cvm.PTR.off, true);

  const readHash = (off) =>
    cvm.PTR.buf.subarray(off, off + 32);

  cvm.FC ??= new Map();
  cvm.HC ??= new Map();
  cvm.OV ??= new Map();
  cvm.ST ??= [];

  const download = async (fileHash) => {
    const k = hex(fileHash);

    if (!cvm.FC.has(k)) {
      cvm.FC.set(k, await cvm.download_file(fileHash));
    }

    return cvm.FC.get(k);
  };

  const upload = async (file) =>
    unhex((await apiJSON(`${apiBase}/api/upload`, {
      method: "POST",
      body: file,
    })).hash);

  const userGet = async (keyHash) =>
    unhex((await apiJSON(
      `${apiBase}/api/user/get/${hex(cvm.USER)}/${hex(keyHash)}`
    )).value);

  const userSet = async (keyHash, fileHash) =>
    apiJSON(`${apiBase}/api/user/set/${hex(cvm.USER)}/${hex(keyHash)}/${hex(fileHash)}`, {
      method: "POST",
    });

  const addEdge = async (parentHash, childHash) =>
    apiJSON(`${apiBase}/api/edge/${hex(parentHash)}/${hex(childHash)}`, {
      method: "POST",
    });

  const vote = async (parentHash, childHash) => {
    if (!cvm.USER) {
      throw new Error("need user id");
    }

    await apiJSON(`${apiBase}/api/vote/${hex(cvm.USER)}/${hex(parentHash)}/${hex(childHash)}`, {
      method: "POST",
    });
  };

  const children = async (parentHash) => {
    const data = await apiJSON(`${apiBase}/api/children/${hex(parentHash)}`);
    return data.children;
  };

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
    if (!cvm.USER) {
      throw new Error("need user id");
    }

    for (const [keyHex, file] of cvm.OV) {
      const fileHash = await upload(file);

      await userSet(unhex(keyHex), fileHash);

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
    localStorage.setItem("CVM_USER", cvm.USER);
  };

  cvm.executeBlock = async () => {
    for (;;) {
      const file = await cvm.gethashhashfile(readHash(cvm.PTR.off + 4));

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
    cvm.PTR.off += 36;

    for (let n; n = read32(); cvm.PTR.off += 4 + n);

    return cvm.executeBlock();
  };

  if (globalThis.HTMLJS_EDITOR_STARTED) {
    return;
  }

  globalThis.HTMLJS_EDITOR_STARTED = true;
  globalThis.continueExecution = () => cvm.resume();

  const makeBlock = (hashes) => {
    const out = new Uint8Array(hashes.length * 36);

    hashes.forEach((h, i) => {
      out.set(unhex(h), i * 36 + 4);
    });

    return out;
  };

  const parseBlock = (file) => {
    const out = [];
    const view = new DataView(file.buffer, file.byteOffset, file.byteLength);

    for (let off = 0; off + 36 <= file.length;) {
      const n = view.getUint32(off, true);

      if (n !== 0) {
        break;
      }

      out.push(hex(file.subarray(off + 4, off + 36)));
      off += 36;
    }

    return out;
  };

  const keyHash = async (text) => cvm.sha256(text);

  const loadKeyFile = async (keyHex) =>
    cvm.gethashhashfile(unhex(keyHex));

  const preview = async (keyHex) => {
    try {
      const file = await loadKeyFile(keyHex);

      if (file[0] === 0) {
        return parseBlock(file).map(short).join("\n");
      }

      return dec.decode(file).slice(0, 500);
    } catch (err) {
      return String(err.message || err);
    }
  };

  const css = document.createElement("style");
  css.textContent = `
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: #f6f7f8;
      color: #18212b;
    }
    button, input, textarea {
      font: inherit;
    }
    button {
      border: 1px solid #cbd3dc;
      border-radius: 6px;
      background: white;
      padding: 7px 10px;
      cursor: pointer;
    }
    button.primary {
      background: #126b68;
      border-color: #126b68;
      color: white;
    }
    input, textarea {
      width: 100%;
      border: 1px solid #cbd3dc;
      border-radius: 6px;
      background: white;
      padding: 8px;
    }
    textarea {
      min-height: 260px;
      font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
      font-size: 13px;
      line-height: 1.45;
      resize: vertical;
    }
    .top {
      display: flex;
      gap: 8px;
      align-items: center;
      padding: 10px;
      background: white;
      border-bottom: 1px solid #dbe1e8;
    }
    .brand {
      font-weight: 700;
      white-space: nowrap;
    }
    .status {
      min-width: 0;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
      color: #5d6a79;
      font-size: 13px;
    }
    .main {
      display: grid;
      grid-template-columns: 320px 1fr;
      min-height: calc(100vh - 53px);
    }
    .pane {
      padding: 12px;
      min-width: 0;
      overflow: auto;
      border-right: 1px solid #dbe1e8;
    }
    .pane:last-child {
      border-right: 0;
    }
    .row {
      display: flex;
      gap: 8px;
      margin-bottom: 8px;
      align-items: center;
    }
    .list {
      display: grid;
      gap: 8px;
      margin-top: 10px;
    }
    .item {
      border: 1px solid #d5dde6;
      border-radius: 8px;
      background: white;
      padding: 8px;
      cursor: grab;
    }
    .item.active {
      border-color: #126b68;
      box-shadow: 0 0 0 2px rgba(18, 107, 104, .12);
    }
    .title {
      font-weight: 650;
      overflow-wrap: anywhere;
    }
    .meta {
      color: #657386;
      font-size: 12px;
      margin-top: 4px;
      overflow-wrap: anywhere;
    }
    .preview {
      white-space: pre-wrap;
      overflow-wrap: anywhere;
      font-size: 12px;
      margin-top: 6px;
      max-height: 120px;
      overflow: hidden;
    }
    .flow {
      min-height: 220px;
      border: 1px dashed #9fabb9;
      border-radius: 8px;
      background: white;
      padding: 10px;
      display: grid;
      gap: 8px;
      align-content: start;
    }
    .flow.over {
      background: #edf8f7;
      border-color: #126b68;
    }
    .block {
      border: 1px solid #d5dde6;
      border-radius: 8px;
      background: #fbfcfd;
      padding: 8px;
      display: grid;
      grid-template-columns: 1fr auto;
      gap: 8px;
      align-items: center;
    }
    @media (max-width: 850px) {
      .top { flex-wrap: wrap; }
      .main { grid-template-columns: 1fr; }
      .pane { border-right: 0; border-bottom: 1px solid #dbe1e8; }
    }
  `;
  document.head.appendChild(css);

  document.body.innerHTML = `
    <div class="top">
      <div class="brand">HTMLJS</div>
      <button id="run" class="primary">Run</button>
      <button id="save">Save</button>
      <button id="publish">Publish</button>
      <input id="idFile" type="file" accept=".bin,application/octet-stream" style="max-width:180px">
      <div id="status" class="status">ready</div>
    </div>
    <div class="main">
      <div class="pane">
        <div class="row">
          <input id="parent" value="HTMLJSroot">
          <button id="openParent">Open</button>
        </div>
        <div class="list" id="children"></div>
      </div>
      <div class="pane">
        <div class="row">
          <input id="active" value="HTMLJSstart">
          <button id="openActive">Load</button>
          <button id="vote">Vote</button>
        </div>
        <div class="row">
          <button id="asFlow">Flow</button>
          <button id="asSource">Source</button>
        </div>
        <div id="flow" class="flow"></div>
        <textarea id="source" style="display:none"></textarea>
      </div>
    </div>
  `;

  const $ = (id) => document.getElementById(id);
  const setStatus = (text) => $("status").textContent = text;

  const savedUser = localStorage.getItem("CVM_USER");
  if (savedUser) {
    cvm.user(savedUser);
  }

  let parentHex = hex(await keyHash("HTMLJSroot"));
  let activeHex = hex(await keyHash("HTMLJSstart"));
  let selectedHex = activeHex;
  let mode = "flow";
  let flowItems = [];

  const resolveKey = async (text) =>
    /^[0-9a-fA-F]{64}$/.test(text.trim())
      ? text.trim().toLowerCase()
      : hex(await keyHash(text.trim()));

  const renderFlow = () => {
    const box = $("flow");
    box.innerHTML = "";

    flowItems.forEach((h, i) => {
      const item = document.createElement("div");
      item.className = "block";
      item.innerHTML = `
        <div>
          <div class="title">${short(h)}</div>
          <div class="meta">${h}</div>
        </div>
        <button>Remove</button>
      `;
      item.querySelector("button").onclick = () => {
        flowItems.splice(i, 1);
        renderFlow();
      };
      box.appendChild(item);
    });
  };

  const loadActive = async () => {
    activeHex = await resolveKey($("active").value);
    selectedHex = activeHex;

    const file = await loadKeyFile(activeHex);

    if (file[0] === 0) {
      mode = "flow";
      flowItems = parseBlock(file);
      $("flow").style.display = "";
      $("source").style.display = "none";
      renderFlow();
    } else {
      mode = "source";
      $("source").value = dec.decode(file);
      $("flow").style.display = "none";
      $("source").style.display = "";
    }

    setStatus(`loaded ${short(activeHex)}`);
  };

  const renderChildren = async () => {
    parentHex = await resolveKey($("parent").value);
    const list = $("children");
    list.innerHTML = "";

    for (const child of await children(unhex(parentHex))) {
      const item = document.createElement("div");
      item.className = "item";
      item.draggable = true;
      item.dataset.hash = child.hash;

      item.innerHTML = `
        <div class="title">${short(child.hash)}</div>
        <div class="meta">score ${child.score}</div>
        <div class="preview"></div>
      `;

      item.querySelector(".preview").textContent = await preview(child.hash);

      item.onclick = async () => {
        selectedHex = child.hash;
        activeHex = child.hash;
        $("active").value = child.hash;
        await loadActive();
      };

      item.ondragstart = (ev) => {
        ev.dataTransfer.setData("text/plain", child.hash);
      };

      list.appendChild(item);
    }

    setStatus(`children ${short(parentHex)}`);
  };

  const currentFile = () =>
    mode === "flow"
      ? makeBlock(flowItems)
      : enc.encode($("source").value);

  $("openParent").onclick = renderChildren;
  $("openActive").onclick = loadActive;

  $("asFlow").onclick = () => {
    mode = "flow";
    $("flow").style.display = "";
    $("source").style.display = "none";
    renderFlow();
  };

  $("asSource").onclick = () => {
    mode = "source";
    $("flow").style.display = "none";
    $("source").style.display = "";
  };

  $("save").onclick = async () => {
    cvm.override(unhex(activeHex), currentFile());
    await cvm.Modify_override();
    setStatus(`saved override ${short(activeHex)}`);
  };

  $("publish").onclick = async () => {
    const fileHash = await upload(currentFile());
    await addEdge(unhex(activeHex), fileHash);
    cvm.HC.delete(activeHex);
    setStatus(`published ${short(activeHex)}`);
  };

  $("run").onclick = async () => {
    cvm.PTR = {
      buf: currentFile(),
      off: 0,
    };

    await cvm.executeBlock();
  };

  $("vote").onclick = async () => {
    await vote(unhex(parentHex), unhex(selectedHex));
    await renderChildren();
  };

  $("idFile").onchange = async () => {
    const file = $("idFile").files[0];
    if (!file) return;

    const id = new Uint8Array(await file.arrayBuffer());
    if (id.length !== 32) {
      throw new Error("id.bin must be 32 bytes");
    }

    cvm.user(id);
    setStatus(`user ${short(hex(id))}`);
  };

  $("flow").ondragover = (ev) => {
    ev.preventDefault();
    $("flow").classList.add("over");
  };

  $("flow").ondragleave = () => {
    $("flow").classList.remove("over");
  };

  $("flow").ondrop = (ev) => {
    ev.preventDefault();
    $("flow").classList.remove("over");

    const h = ev.dataTransfer.getData("text/plain");
    if (!h) return;

    flowItems.push(h);
    renderFlow();
  };

  await renderChildren();
  await loadActive();

  return cvm.resume();
})();
"""


CONTINUE_JS = r"""
CVM.PTR.off = 0;
return CVM.executeBlock();
"""


def sha256_bytes(data: bytes) -> bytes:
    return hashlib.sha256(data).digest()


def sha256_text(text: str) -> bytes:
    return sha256_bytes(text.encode("utf-8"))


def hx(data: bytes) -> str:
    return data.hex()


def json_request(url: str, method: str = "GET", body: bytes | None = None) -> dict:
    req = urllib.request.Request(url, data=body, method=method)

    try:
        with urllib.request.urlopen(req) as resp:
            raw = resp.read()
    except urllib.error.HTTPError as err:
        raw = err.read()
        msg = raw.decode("utf-8", errors="replace")
        raise RuntimeError(f"{method} {url} HTTP {err.code}: {msg}") from err

    data = json.loads(raw.decode("utf-8"))

    if not data.get("ok"):
        raise RuntimeError(f"{method} {url}: {data.get('error', data)}")

    return data.get("data")


def upload(api: str, data: bytes) -> bytes:
    out = json_request(f"{api}/api/upload", method="POST", body=data)
    return bytes.fromhex(out["hash"])


def add_edge(api: str, parent: bytes, child: bytes) -> None:
    json_request(
        f"{api}/api/edge/{hx(parent)}/{hx(child)}",
        method="POST",
        body=b"",
    )


def vote_edge(api: str, user: bytes, parent: bytes, child: bytes) -> None:
    json_request(
        f"{api}/api/vote/{hx(user)}/{hx(parent)}/{hx(child)}",
        method="POST",
        body=b"",
    )


def block_record(key_name: str) -> bytes:
    return struct.pack("<I", 0) + sha256_text(key_name)


def make_start_bin() -> bytes:
    return block_record("start") + block_record("continue")


def read_user_id(path: str) -> bytes:
    with open(path, "rb") as f:
        user = f.read()
    if len(user) != 32:
        raise RuntimeError(f"{path} must be exactly 32 bytes")
    return user


def upload_mapping(
    api: str,
    key_name: str,
    file_name: str,
    source: bytes,
    user: bytes | None = None,
) -> tuple[bytes, bytes]:
    key_hash = sha256_text(key_name)
    file_hash = upload(api, source)
    add_edge(api, key_hash, file_hash)

    if user is not None:
        vote_edge(api, user, key_hash, file_hash)

    print(f"{key_name} - {file_name}")
    print(f"  key  {hx(key_hash)}")
    print(f"  file {hx(file_hash)}")
    return key_hash, file_hash


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--api", default=API_DEFAULT)
    parser.add_argument("--id-bin", default="", help="registered id.bin path, to vote new edges to the top")
    parser.add_argument("--root", action="store_true")
    parser.add_argument("--write-start-bin", default="")
    args = parser.parse_args()

    api = args.api.rstrip("/")

    user = None
    if args.id_bin:
        user = read_user_id(args.id_bin)
        print(f"using user {hx(user)}")

    print(f"api {api}")

    start_key, _ = upload_mapping(
        api,
        "start",
        "embedded:start.js",
        START_JS.strip().encode("utf-8"),
        user,
    )

    continue_key, _ = upload_mapping(
        api,
        "continue",
        "embedded:continue.js",
        CONTINUE_JS.strip().encode("utf-8"),
        user,
    )

    start_bin = make_start_bin()

    if args.write_start_bin:
        with open(args.write_start_bin, "wb") as f:
            f.write(start_bin)
        print(f"wrote {args.write_start_bin}")

    htmljs_start_key = sha256_text("HTMLJSstart")
    start_bin_hash = upload(api, start_bin)
    add_edge(api, htmljs_start_key, start_bin_hash)

    if user is not None:
        vote_edge(api, user, htmljs_start_key, start_bin_hash)

    print("HTMLJSstart - embedded:start.bin")
    print(f"  key  {hx(htmljs_start_key)}")
    print(f"  file {hx(start_bin_hash)}")

    if args.root:
        root_key = sha256_text("HTMLJSroot")

        add_edge(api, root_key, htmljs_start_key)
        add_edge(api, root_key, start_key)
        add_edge(api, root_key, continue_key)

        if user is not None:
            vote_edge(api, user, root_key, htmljs_start_key)
            vote_edge(api, user, root_key, start_key)
            vote_edge(api, user, root_key, continue_key)

        print("HTMLJSroot")
        print(f"  key         {hx(root_key)}")
        print(f"  HTMLJSstart {hx(htmljs_start_key)}")
        print(f"  start       {hx(start_key)}")
        print(f"  continue    {hx(continue_key)}")

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as err:
        print(f"error: {err}", file=sys.stderr)
        raise SystemExit(1)