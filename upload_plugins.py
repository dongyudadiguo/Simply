#!/usr/bin/env python3
import os
import socket
import struct

HOST = "127.0.0.1"
PORT = 8000

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
PLUGINS_DIR = os.path.join(ROOT_DIR, "plugins")

def get_plugin_names():
    names = []
    if os.path.exists(PLUGINS_DIR):
        for f in os.listdir(PLUGINS_DIR):
            if f.endswith(".c"):
                names.append(f[:-2])
    if not names:
        names = ["get", "set", "gget", "gset", "cond", "condrerun", "handrun", "rerun", "add", "init"]
    return sorted(list(set(names)))

def pack_payload(tokens):
    buf = bytearray()
    for t in tokens:
        raw = t.encode("utf-8")
        buf += struct.pack("<I", len(raw)) + raw
    return bytes(buf)

def upload_to_server(key: bytes, payload: bytes):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.connect((HOST, PORT))
        op = struct.pack("B", 3)
        k_buf = struct.pack("<I", len(key)) + key
        p_buf = struct.pack("<I", len(payload)) + payload
        s.sendall(op + k_buf + p_buf)
        res = s.recv(4)
        print(f"[+] 成功上传 {len(tokens)} 个插件名到服务器 (Key: 空, 共 {len(payload)} 字节)")
    finally:
        s.close()

if __name__ == "__main__":
    tokens = get_plugin_names()
    print(f"[*] 扫描到插件列表: {tokens}")
    payload = pack_payload(tokens)
    upload_to_server(b"", payload)
