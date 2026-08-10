# upload_boot.py —— 向服务器上传 boot 到零大小 data（空 key）下
# 上传 data（8 字节，最低限度 [n][name]）：
#   [4B token长][boot]  → 04 00 00 00 62 6f 6f 74
# vm fetch(空key) → iter_tokens 容错解析 name="boot"（无 payload 字段）→ 加载 sha256("boot") 插件
import socket, struct

HOST, PORT = "127.0.0.1", 8000

def recv_all(s, n):                          # 精确读满 n 字节
    data = b""
    while len(data) < n:
        chunk = s.recv(n - len(data))
        if not chunk: raise ConnectionError("连接被关闭")
        data += chunk
    return data

def upload(key, data):                       # 服务端 op=3：上传数据
    with socket.create_connection((HOST, PORT), timeout=3) as s:
        s.sendall(b"\x03" + struct.pack("<I", len(key)) + key +
                  struct.pack("<I", len(data)) + data)
        return struct.unpack("<I", recv_all(s, 4))[0]

# 最低限度：4 字节数字 4 + "boot"
block = struct.pack("<I", 4) + b"boot"
assert len(block) == 8, len(block)           # 确保总共 8 字节
print("data:", block.hex(), "长度:", len(block))

idx = upload(b"", block)                     # 上传到空 key（零大小 data）
print("已上传到零大小 data（空 key），idx =", idx)
