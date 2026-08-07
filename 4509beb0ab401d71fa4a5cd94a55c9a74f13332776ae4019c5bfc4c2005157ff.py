# 1553cc62....py —— 引导插件（原 boot_dll.py，改名为 sha256("editor")）
# 逻辑：生成/读取机器 id -> 首次上传引导块 -> 用公共 block.run_loop 从 id key 引导执行
# 协议：op1 投票 / op2 取数据 / op3 上传（与 server 最小协议对齐，op4 已删）
import os, sys, struct     # 路径/系统/编解码
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # 本目录加入搜索路径
import socket              # TCP 连接本地服务器
from block import recv_all, fetch, next_key, load_run, run_loop   # 复用公共 block 逻辑（vm 的为准）

HOST, PORT = "127.0.0.1", 8000   # 本地服务器地址与端口
ID_FILE = "id.bin"               # 机器 id 文件（32 字节随机）
HERE = os.path.dirname(os.path.abspath(__file__))   # 本文件所在目录（插件放一起）

def upload(key, data):                       # 服务端 op=3：上传数据
    with socket.create_connection((HOST, PORT), timeout=3) as s:   # 连服务器（3 秒超时）
        s.sendall(b"\x03" + struct.pack("<I", len(key)) + key +   # 发 [op=3][key长][key]
                  struct.pack("<I", len(data)) + data)             #    [data长][data]
        return struct.unpack("<I", recv_all(s, 4))[0]              # 读回 4 字节 idx

def vote(key, idx):                          # 服务端 op=1：给某条数据投票（平票时票数高者胜）
    with socket.create_connection((HOST, PORT), timeout=3) as s:   # 连服务器（3 秒超时）
        s.sendall(b"\x01" + struct.pack("<I", len(key)) + key + struct.pack("<I", idx))  # 发 [op=1][key长][key][idx]
        return struct.unpack("<I", recv_all(s, 4))[0]              # 读回 4 字节新票数

def get_id():
    if os.path.exists(ID_FILE):              # 已有 id 直接用
        return open(ID_FILE, "rb").read()    # 读回 32 字节 id
    new_id = os.urandom(32)                  # 首次运行：生成 32 字节随机 id
    open(ID_FILE, "wb").write(new_id)        # 保存到 id.bin
    # 初始引导块，字节与原 C 版完全一致：[6]editor[0][5]rerun[0][0]
    block = (bytes([6, 0, 0, 0]) + b"editor" + bytes([0, 0, 0, 0]) +   # editor 指令（token_len=6, data 空）
             bytes([5, 0, 0, 0]) + b"rerun" + bytes([0, 0, 0, 0]) +    # rerun 指令（token_len=5, data 空）
             bytes([0, 0, 0, 0]))                                      # 块结束标记（token_len=0）
    upload(new_id, block)                    # 把引导块上传到 id key
    return new_id                            # 返回 id

def run():
    run_loop(get_id())                       # 从 id key 引导执行（复用公共逻辑）

if __name__ == "__main__":
    run()                                    # 入口：启动引导
