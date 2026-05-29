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
(() => {
  const cvm = CVM;
  const enc = new TextEncoder();
  const dec = new TextDecoder();

  const ZERO =
    "0000000000000000000000000000000000000000000000000000000000000000";

  const hex = (x) =>
    typeof x === "string"
      ? x
      : [...x].map((b) => b.toString(16).padStart(2, "0")).join("");

  const unhex = (h) =>
    new Uint8Array(h.match(/../g).map((x) => parseInt(x, 16)));

  const oneLine = (bytes) =>
    dec.decode(bytes)
      .replace(/\s+/g, " ")
      .trim();

  const api = (path, opt) =>
    fetch(`${apiBase}${path}`, opt).then((r) => r.json());

  const file = async (h) =>
    new Uint8Array(await fetch(`${apiBase}/api/file/${h}`).then((r) => r.arrayBuffer()));

  const children = async (h) => {
    const j = await api(`/api/children/${h}`);
    if (!j.ok) throw new Error(j.error || "children failed");
    return j.data.children || [];
  };

  const upload = async (bytes) => {
    const j = await api(`/api/upload`, {
      method: "POST",
      body: bytes,
    });
    if (!j.ok) throw new Error(j.error || "upload failed");
    return j.data.hash;
  };

  const addEdge = async (parent, child) => {
    const j = await api(`/api/edge/${parent}/${child}`, { method: "POST" });
    if (!j.ok) throw new Error(j.error || "edge failed");
  };

  document.body.innerHTML = `
    <main id="cvmFileBrowser">
      <header>
        <button id="up" title="返回上级">↑</button>
        <input id="where" spellcheck="false" />
        <button id="go">打开</button>
      </header>

      <section id="list"></section>

      <footer>
        <input id="text" placeholder="一行文本文件内容" />
        <button id="save">上传到当前节点</button>
      </footer>
    </main>
  `;

  const css = document.createElement("style");
  css.textContent = `
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
      background: #f6f6f3;
      color: #191919;
    }
    #cvmFileBrowser {
      min-height: 100vh;
      display: grid;
      grid-template-rows: auto 1fr auto;
    }
    header, footer {
      display: flex;
      gap: 8px;
      padding: 10px;
      border-bottom: 1px solid #d8d8d2;
      background: #ffffff;
    }
    footer {
      border-top: 1px solid #d8d8d2;
      border-bottom: 0;
    }
    input {
      min-width: 0;
      flex: 1;
      height: 34px;
      padding: 0 9px;
      border: 1px solid #bdbdb7;
      border-radius: 4px;
      font: inherit;
      background: #fff;
    }
    button {
      height: 34px;
      padding: 0 10px;
      border: 1px solid #a9a9a2;
      border-radius: 4px;
      background: #ededdf;
      color: #111;
      font: inherit;
      cursor: pointer;
    }
    button:hover { background: #e1e1d0; }
    #list {
      padding: 10px;
      overflow: auto;
    }
    .row {
      display: grid;
      grid-template-columns: 72px 1fr;
      gap: 10px;
      align-items: center;
      padding: 7px 8px;
      border-bottom: 1px solid #e1e1dc;
      cursor: pointer;
    }
    .row:hover { background: #ffffff; }
    .hash {
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }
    .content {
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
      color: #54544d;
    }
    .empty, .err {
      padding: 12px 8px;
      color: #6b6b64;
    }
    .err { color: #a32020; }
  `;
  document.head.appendChild(css);

  const el = {
    up: document.getElementById("up"),
    where: document.getElementById("where"),
    go: document.getElementById("go"),
    list: document.getElementById("list"),
    text: document.getElementById("text"),
    save: document.getElementById("save"),
  };

  let cur = ZERO;
  const stack = [];

  const render = async (h, push = true) => {
    if (push && cur !== h) stack.push(cur);
    cur = h;
    el.where.value = h;
    el.list.innerHTML = `<div class="empty">loading...</div>`;

    try {
      const cs = await children(h);

      if (!cs.length) {
        const bytes = await file(h);
        el.list.innerHTML = `
          <div class="row">
            <div class="hash">file</div>
            <div class="content">${escapeHtml(oneLine(bytes))}</div>
          </div>
        `;
        return;
      }

      const rows = await Promise.all(cs.map(async (c) => {
        let text = "";
        try {
          text = oneLine(await file(c.hash));
        } catch {
          text = "";
        }

        return `
          <div class="row" data-hash="${c.hash}">
            <div class="hash">${c.hash.slice(0, 12)}...</div>
            <div class="content">${escapeHtml(text)}</div>
          </div>
        `;
      }));

      el.list.innerHTML = rows.join("");
    } catch (e) {
      el.list.innerHTML = `<div class="err">${escapeHtml(String(e.message || e))}</div>`;
    }
  };

  const escapeHtml = (s) =>
    String(s).replace(/[&<>"']/g, (c) => ({
      "&": "&amp;",
      "<": "&lt;",
      ">": "&gt;",
      '"': "&quot;",
      "'": "&#39;",
    }[c]));

  el.list.onclick = (e) => {
    const row = e.target.closest("[data-hash]");
    if (row) render(row.dataset.hash);
  };

  el.go.onclick = () => {
    const h = el.where.value.trim().toLowerCase();
    if (/^[0-9a-f]{64}$/.test(h)) render(h);
  };

  el.up.onclick = () => {
    if (stack.length) render(stack.pop(), false);
  };

  el.save.onclick = async () => {
    const text = el.text.value;
    if (!text) return;

    el.save.disabled = true;

    try {
      const h = await upload(enc.encode(text));
      await addEdge(cur, h);
      el.text.value = "";
      await render(cur, false);
    } finally {
      el.save.disabled = false;
    }
  };

  el.where.onkeydown = (e) => {
    if (e.key === "Enter") el.go.click();
  };

  el.text.onkeydown = (e) => {
    if (e.key === "Enter") el.save.click();
  };

  render(ZERO, false);
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