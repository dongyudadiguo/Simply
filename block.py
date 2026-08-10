# block.py —— 公共：block 协议 + 引导/执行（vm 和 boot 共用，以 vm 的为准）
# 设计：完全不做错误/崩溃处理 —— 任何异常直接冒泡（自然退出/报错）
import hashlib          # 计算 token 的 sha256 作为插件文件名
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

def load_src(key):                           # key 的 sha256 十六进制就是插件文件名
    path = os.path.join(HERE, hashlib.sha256(key).hexdigest() + ".py")  # 拼接插件路径（不存在即抛异常）
    return open(path, encoding="utf-8").read()   # 读插件源码（最直接）

def iter_tokens(blk):                        # 解析块 → (name, payload) 序列
    i = 0
    while i + 4 <= len(blk):
        n = struct.unpack_from("<I", blk, i)[0]; i += 4
        if not n: break
        name = blk[i:i+n].decode("utf-8","replace"); i += n
        d = struct.unpack_from("<I", blk, i)[0]; i += 4
        yield name, blk[i:i+d]; i += d

def run_token(name, payload=b""):            # 单个 token 接棒：命中插件则 exec 顶层，否则下钻其块
    key = name.encode()
    try:
        src = load_src(key)                  # 命中插件
    except OSError:                          # 无插件 → 该 token 是块引用，下钻执行其块
        run_block(key)
        return
    exec(src, {"payload": payload})          # 顶层直接执行（payload 注入）

def run_block(start_key=b""):                 # 执行块：遍历 token，逐个 run_token 接棒
    for name, payload in iter_tokens(fetch(start_key)):
        run_token(name, payload)
