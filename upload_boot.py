# upload_boot.py —— 向服务器上传 boot 引导块到零大小 data（空 key）下
# 空 key 块 = [boot] + 全部插件名（payload 空）：
#   [4B token长][name][4B payload长][payload] ... [0]
# - 引导：run_block(空key) 用 next_key 只取第一条 name（boot）→ boot 插件接管
# - 补全：collect() 从空 key 递归收集所有 token 名 → 插件名成为补全匹配来源
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

# 插件名清单（boot 引导必须第一：next_key 只取第一条）
NAMES = ["boot", "editor", "rerun", "add", "read", "set", "cond", "handrun", "condrerun",
         "push_int", "in-int", "out", "rand", "gt", "lt", "eq", "mul", "ret_int"]
block = b""
for n in NAMES:                              # 每个 token：payload 空（零大小 data）
    b = n.encode()
    block += struct.pack("<I", len(b)) + b + struct.pack("<I", 0)
block += struct.pack("<I", 0)                # 块结束标记
print("data 长度:", len(block), "token 数:", len(NAMES))

idx = upload(b"", block)                     # 上传到空 key（零大小 data）
print("已上传到零大小 data（空 key），idx =", idx)
