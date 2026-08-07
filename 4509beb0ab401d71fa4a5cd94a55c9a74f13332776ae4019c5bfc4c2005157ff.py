# 4509beb0ab401d71fa4a5cd94a55c9a74f13332776ae4019c5bfc4c2005157ff.py —— boot 插件（token="boot" → sha256 命名）
# 内容：引导器 —— 生成/读取机器 id -> 上传引导块 -> 从 id key 引导执行
# 直接代码（不加 run 层）：import block 后直接调用 run_loop(get_id())
import os, struct          # 文件/编解码
import socket              # TCP 连接
from block import recv_all, run_loop   # 公共逻辑（vm 主脚本已把目录放入 sys.path）

ID_FILE = "id.bin"                       # 机器 id 文件
HOST, PORT = "127.0.0.1", 8000           # 本地服务器地址与端口

def upload(key, data):                   # 服务端 op=3：上传数据
    with socket.create_connection((HOST, PORT), timeout=3) as s:
        s.sendall(b"\x03" + struct.pack("<I", len(key)) + key +
                  struct.pack("<I", len(data)) + data)
        return struct.unpack("<I", recv_all(s, 4))[0]

def vote(key, idx):                      # 服务端 op=1：投票
    with socket.create_connection((HOST, PORT), timeout=3) as s:
        s.sendall(b"\x01" + struct.pack("<I", len(key)) + key + struct.pack("<I", idx))
        return struct.unpack("<I", recv_all(s, 4))[0]

def get_id():
    if os.path.exists(ID_FILE):          # 已有 id 直接用
        return open(ID_FILE, "rb").read()
    new_id = os.urandom(32)              # 生成 32 字节 id
    open(ID_FILE, "wb").write(new_id)
    block = (bytes([6, 0, 0, 0]) + b"editor" + bytes([0, 0, 0, 0]) +   # 引导块 [editor][rerun]
             bytes([5, 0, 0, 0]) + b"rerun" + bytes([0, 0, 0, 0]) +
             bytes([0, 0, 0, 0]))
    upload(new_id, block)                # 上传引导块到 id key
    return new_id

run_loop(get_id())                       # 直接执行：从 id key 引导（接管控制流）
