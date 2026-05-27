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

'''

CONTINUE_JS = "CVM.PTR.off = 0;\nreturn CVM.executeBlock();\n"


def sha(b: bytes) -> bytes:
    return hashlib.sha256(b).digest()


def key(name: str) -> bytes:
    return sha(name.encode())


def block(names) -> bytes:
    return b"".join(struct.pack("<I", 0) + key(name) for name in names)


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

    raise SystemExit("id.bin 必须是 32字节 raw id，或 64位 hex")


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
        obj = self.call("POST", "/api/upload", data)
        return obj["data"]["hash"], obj

    def edge(self, parent: str, child: str):
        return self.call("POST", f"/api/edge/{parent}/{child}")

    def vote(self, user: str, parent: str, child: str):
        return self.call("POST", f"/api/vote/{user}/{parent}/{child}")


def upload_file_edge_vote(api: API, user: str, parent_name: str, file_name: str, data: bytes):
    parent = key(parent_name).hex()
    local_hash = sha(data).hex()

    uploaded, upload_result = api.upload(data)
    edge_result = api.edge(parent, uploaded)
    vote_result = api.vote(user, parent, uploaded)

    print(f"{parent_name} -> {file_name}")
    print("  parent key :", parent)
    print("  file hash  :", uploaded)
    print("  local hash :", local_hash)
    print("  upload     :", upload_result)
    print("  edge       :", edge_result)
    print("  vote       :", vote_result)
    print()

    return uploaded


def upload_string_children(api: API, user: str, parent_name: str, child_names):
    parent = key(parent_name).hex()
    made = []

    print(f"{parent_name} children")
    print("  parent key :", parent)

    for name in child_names:
        data = name.encode()
        local_hash = sha(data).hex()
        uploaded, upload_result = api.upload(data)

        if uploaded != local_hash:
            raise RuntimeError(f"hash mismatch for {name}")

        edge_result = api.edge(parent, uploaded)

        made.append((name, uploaded))

        print(f"  child      : {name}")
        print(f"    file hash: {uploaded}")
        print(f"    upload   : {upload_result}")
        print(f"    edge     : {edge_result}")

    # 服务器同分时最新 vote 排最前。
    # 为了最终显示顺序等于 child_names，需要倒序投票。
    for name, child_hash in reversed(made):
        vote_result = api.vote(user, parent, child_hash)
        print(f"    vote     : {parent_name} -> {name}: {vote_result}")

    print()
    return made


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

    # VM 启动链仍然是：
    # HTMLJSstart -> start.bin
    # start.bin 内容：0 [start], 0 [continue]
    upload_file_edge_vote(api, user, "start", "start.js", START_JS.encode())
    upload_file_edge_vote(api, user, "continue", "continue.js", CONTINUE_JS.encode())
    upload_file_edge_vote(api, user, "HTMLJSstart", "start.bin", block(["start", "continue"]))

    # 注意：这里没有 root.bin。
    # HTMLJSroot 的 child 直接就是字符串文件的 hash。
    upload_string_children(api, user, "HTMLJSroot", ROOT_CHILDREN)
    upload_string_children(api, user, "Process control", PROCESS_CHILDREN)

    print("完成。联网浏览结构应为：")
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