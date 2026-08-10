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

def encode_toks(ts):                         # 块序列化（toks → bytes）
    out = b""
    for n, p in ts:
        b = n.encode()
        out += struct.pack("<I", len(b)) + b
        pb = p if isinstance(p, bytes) else p.encode()
        out += struct.pack("<I", len(pb)) + pb
    return out + struct.pack("<I", 0)

def flush_pending():                         # 运行前对比哈希：有改动才上传（跳过空 key 系统引导块）
    for k, toks in vmstate.cur.items():
        if not k: continue                   # b"" 是 boot 引导块，不覆盖
        blk = encode_toks(toks)
        try:
            old = fetch(k)                      # 服务器当前版本
        except Exception:
            old = b""
        if hashlib.sha256(blk).digest() != hashlib.sha256(old).digest():
            upload(k, blk)                      # 哈希不同 → 有改动 → 上传

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

def _load_toks(key):                          # 取块并解析 token 流（空 key 引导只取 name）
    blk = fetch(key)
    if key == b"":                            # 引导：boot 块最低限度 [n][name]，只取 name
        return [(next_key(blk).decode("utf-8","replace"), b"")]
    return list(iter_tokens(blk))

def run_block(start_key=b""):                 # 迭代主循环（对齐 while(1) imp()）：显式栈下钻/重置，不递归
    flush_pending()                          # 运行前 flush 改动（每次运行入口）
    cur_key = start_key
    vmstate.cur_key = cur_key                # 暴露当前块 key（editor 定位所在块用，替代 inspect）
    cur_toks = _load_toks(cur_key)
    cur_i = 0
    stack = []                                # 下钻返回栈 [(key, toks, i)]（cond/handrun/块引用）
    while True:                               # —— 迭代执行（不递归、不堆积）——
        if cur_i >= len(cur_toks):            # 当前块走完
            if stack:                         # 弹栈回上层继续
                cur_key, cur_toks, cur_i = stack.pop()
                continue
            break                             # 全部走完 → 结束
        name, payload = cur_toks[cur_i]
        cur_i += 1                            # 默认推进（run_next 语义）
        try:
            src = load_src(name.encode())     # 命中插件
        except OSError:                       # 无插件 → 块引用，下钻其块（压栈）
            stack.append((cur_key, cur_toks, cur_i))
            cur_key = name.encode()
            vmstate.cur_key = cur_key
            cur_toks = _load_toks(cur_key)
            cur_i = 0
            continue
        def run_next():                       # 插件自主接棒：位置已推进（cur_i += 1）
            pass
        def run_block(k):                     # 插件下钻/重跑（迭代，不递归）
            nonlocal cur_key, cur_toks, cur_i
            if k == cur_key:                  # 重跑当前块（rerun：重置位置）
                cur_i = 0
            else:                             # 下钻目标块（cond/handrun/运行：压栈切块）
                stack.append((cur_key, cur_toks, cur_i))
                cur_key = k
                vmstate.cur_key = cur_key
                cur_toks = _load_toks(k)
                cur_i = 0
        try:
            exec(src, {"payload": payload, "run_next": run_next,
                       "run_block": run_block})   # 注入 payload/run_next/run_block
        except SystemExit:                    # 正常结束信号（editor 关闭/ret_int）→ 保存并退出
            flush_pending()
            break
