# block.py —— 公共：block 协议 + 引导/执行（vm 和 boot 共用，以 vm 的为准）
# 设计：完全不做错误/崩溃处理 —— 任何异常直接冒泡（自然退出/报错）
import hashlib          # 计算 token 的 sha256 作为插件文件名
import os               # 拼接插件文件路径
import socket           # TCP 连接本地服务器
import struct           # 编解码 4 字节小端整数（协议头）
import vmstate          # 共享 VM 状态（pending 待上传改动）

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

def upload(key, data):                       # 服务端 op=3：上传数据（覆盖）
    with socket.create_connection((HOST, PORT), timeout=3) as s:
        s.sendall(b"\x03" + struct.pack("<I", len(key)) + key +
                  struct.pack("<I", len(data)) + data)
        return struct.unpack("<I", recv_all(s, 4))[0]

def flush_pending():                         # 运行前检查改动：有待上传就上传并清空
    for k, blk in vmstate.pending.items():
        upload(k, blk)
    vmstate.pending.clear()

def load_src(key):                           # key 的 sha256 十六进制就是插件文件名
    path = os.path.join(HERE, hashlib.sha256(key).hexdigest() + ".py")  # 拼接插件路径（不存在即抛异常）
    return open(path, encoding="utf-8").read()   # 读插件源码（最直接）

def iter_tokens(blk):                        # 解析块 → (name, payload) 序列（严格完整格式，缺字段即越界）
    i = 0
    while i + 4 <= len(blk):
        n = struct.unpack_from("<I", blk, i)[0]; i += 4
        if not n: break
        name = blk[i:i+n].decode("utf-8","replace"); i += n
        d = struct.unpack_from("<I", blk, i)[0]; i += 4
        yield name, blk[i:i+d]; i += d

def _chain(toks, i):                          # 链式自主接棒：当前 token 执行后，插件自主 run_next 继续
    if i >= len(toks): return
    name, payload = toks[i]
    try:
        src = load_src(name.encode())          # 命中插件
    except OSError:                            # 无插件 → 该 token 是块引用，下钻其块后继续链
        run_block(name.encode())
        _chain(toks, i+1)
        return
    def run_next():                            # 插件自主接棒：继续链的下一个 token
        _chain(toks, i+1)
    exec(src, {"payload": payload, "run_next": run_next,
               "run_block": run_block})        # 注入 payload/run_next/run_block

def run_block(start_key=b""):                 # 块入口：运行前 flush 改动，再引导/执行
    flush_pending()                          # 检查改动 → 上传
    blk = fetch(start_key)
    if start_key == b"":                      # 引导：boot 块最低限度 [n][name]，只取 name 走 _chain
        _chain([(next_key(blk).decode("utf-8","replace"), b"")], 0)
        return
    _chain(list(iter_tokens(blk)), 0)
