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