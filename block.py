# block.py —— 公共：block 协议 + 引导/执行（vm 和 boot 共用，以 vm 的为准）
# 设计：完全不做错误/崩溃处理 —— 任何异常直接冒泡（自然退出/报错）
import hashlib          # 计算 token 的 sha256 作为插件文件名
import importlib.util   # 从文件路径动态加载 Python 模块
import os               # 拼接插件文件路径
import socket           # TCP 连接本地服务器
import struct           # 编解码 4 字节小端整数（协议头）

HOST, PORT = "127.0.0.1", 8000   # 本地服务器地址与端口
HERE = os.path.dirname(os.path.abspath(__file__))   # 本文件所在目录（插件放一起）

def recv_all(s, n):                          # 从 socket 精确读满 n 字节
    data = b""                               # 已收到的数据累积
    while len(data) < n:                     # 未收满就继续读
        chunk = s.recv(n - len(data))        # 读剩余需要的字节（可能部分/空）
        data += chunk                        # 拼进累积缓冲区（无断线检查）
    return data                              # 返回完整 n 字节

def fetch(key):                              # 服务端 op=2：按 key 取数据
    with socket.create_connection((HOST, PORT)) as s:   # 连服务器（失败直接抛异常）
        s.sendall(b"\x02" + struct.pack("<I", len(key)) + key)  # 发 [op=2][key长][key]
        return recv_all(s, struct.unpack("<I", recv_all(s, 4))[0])  # 读 [payload长][payload]

def next_key(block):                         # 取 block 第一条 token 作为下一个 key
    return block[4 : 4 + struct.unpack("<I", block[:4])[0]]  # 前4字节是 token 长度

def load_run(key):                           # key 的 sha256 十六进制就是插件文件名
    path = os.path.join(HERE, hashlib.sha256(key).hexdigest() + ".py")  # 拼接插件路径（不存在即抛异常）
    spec = importlib.util.spec_from_file_location("vm_plugin", path)    # 创建模块描述符
    mod = importlib.util.module_from_spec(spec)                          # 创建模块对象
    spec.loader.exec_module(mod)             # 每次重新执行插件文件
    return mod.run                           # 返回插件的 run 函数

def run_loop(start_key=b""):                 # 引导 + 无限执行（vm 的为准，无错误处理）
    key = start_key                          # 引导起点：默认空 key（取引导块）
    while True:                              # 引导循环：拿到插件才跳出
        p = fetch(key)                       # 取当前 key 的块（失败直接冒泡）
        key = next_key(p)                    # 更新 key 为第一条 token
        run = load_run(key)                  # 按 key 的 sha256 加载插件（失败直接冒泡）
        break                                # 拿到 run 后结束引导
    while True:                              # 运行循环：无限执行插件
        run()                                # 执行插件（崩溃直接冒泡退出）
