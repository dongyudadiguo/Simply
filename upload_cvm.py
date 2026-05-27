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