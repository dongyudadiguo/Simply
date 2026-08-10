# block.py —— 公共：block 协议 + 引导/执行（vm 和 boot 共用，以 vm 的为准）
# 设计：完全不做错误/崩溃处理 —— 任何异常直接冒泡（自然退出/报错）
import hashlib          # hashlib：把 token 名算 sha256 作为插件文件名
import os               # os：拼接插件文件路径（HERE 目录下）
import socket           # socket：TCP 连接本地服务器（协议传输）
import struct           # struct：编解码 4 字节小端整数（协议头/块内长度字段）
import vmstate          # vmstate：共享 VM 状态（cur 编辑缓存、cur_key 当前块 key）

HOST, PORT = "127.0.0.1", 8000   # 本地服务器地址与端口（裸 TCP）
HERE = os.path.dirname(os.path.abspath(__file__))   # 本文件所在目录（插件和本文件放一起）

def recv_all(s, n):                          # 从 socket 精确读满 n 字节（协议定长读）
    data = b""                               # 已收到的数据累积缓冲
    while len(data) < n:                     # 未收满就继续循环读
        chunk = s.recv(n - len(data))        # 读剩余需要的字节数（可能只到一部分/空）
        data += chunk                        # 拼进累积缓冲区（不做断线检查，异常直接冒泡）
    return data                              # 返回完整的 n 字节

def fetch(key):                              # 服务端 op=2：按 key 取数据
    with socket.create_connection((HOST, PORT)) as s:   # 连服务器（失败直接抛异常）
        s.sendall(b"\x02" + struct.pack("<I", len(key)) + key)  # 发 [op=2][key长][key]
        return recv_all(s, struct.unpack("<I", recv_all(s, 4))[0])  # 读 [payload长] 再读 [payload]

def next_key(block):                         # 取 block 第一条 token 的名字作为下一个 key
    return block[4 : 4 + struct.unpack("<I", block[:4])[0]]  # 前4字节是第一个 token 名长度，取名字段

def upload(key, data):                       # 服务端 op=3：上传数据（覆盖同 key）
    with socket.create_connection((HOST, PORT), timeout=3) as s:   # 连服务器（3 秒超时）
        s.sendall(b"\x03" + struct.pack("<I", len(key)) + key +   # 发 [op=3][key长][key]
                  struct.pack("<I", len(data)) + data)             # 再发 [data长][data]
        return struct.unpack("<I", recv_all(s, 4))[0]              # 读回 4 字节 idx（服务器序号）

def encode_toks(ts):                         # 块序列化：toks → bytes（upload/flush 用）
    out = b""                                # 输出缓冲
    for n, p in ts:                          # 遍历每个 token：(name, payload)
        b = n.encode()                       # token 名编码为 bytes
        out += struct.pack("<I", len(b)) + b # 写 [名长][名]
        pb = p if isinstance(p, bytes) else p.encode()   # payload 保持 bytes（handrun 二进制）或转码
        out += struct.pack("<I", len(pb)) + pb           # 写 [payload长][payload]
    return out + struct.pack("<I", 0)        # 块结束标记（token 长度 0）

def flush_pending():                         # 运行前对比哈希：有改动才上传（跳过空 key 系统引导块）
    for k, toks in vmstate.cur.items():      # 遍历共享 cur（key → toks 引用，editor 编辑天然共享）
        if not k: continue                   # b"" 是 boot 引导块（空 key），不覆盖
        blk = encode_toks(toks)              # 把当前 toks 序列化成块
        try:
            old = fetch(k)                   # 取服务器当前版本
        except Exception:
            old = b""                        # 服务器没有该 key → 视为旧版为空
        if hashlib.sha256(blk).digest() != hashlib.sha256(old).digest():   # 哈希不同 = 有改动
            upload(k, blk)                   # 上传新版本（覆盖）

def load_src(key):                           # 插件查找：key 的 sha256 十六进制 = 插件文件名
    path = os.path.join(HERE, hashlib.sha256(key).hexdigest() + ".py")  # 拼插件路径（不存在即抛 OSError）
    return open(path, encoding="utf-8").read()   # 读插件源码（最直接，exec 顶层跑）

def iter_tokens(blk):                        # 解析块 → (name, payload) 生成器（严格完整格式，缺字段越界）
    i = 0                                    # 解析偏移
    while i + 4 <= len(blk):                 # 还剩至少 4 字节可读 token 长度
        n = struct.unpack_from("<I", blk, i)[0]; i += 4   # 读 token 名长度并前进
        if not n: break                      # n=0 → 块结束标记，停止
        name = blk[i:i+n].decode("utf-8","replace"); i += n   # 读名字段并解码
        d = struct.unpack_from("<I", blk, i)[0]; i += 4      # 读 payload 长度并前进
        yield name, blk[i:i+d]; i += d       # 产出 (name, payload bytes)，前进到下一 token

def _load_toks(key):                          # 取块并解析成 token 流（空 key 引导只取 name）
    blk = fetch(key)                          # 从服务器取块数据
    if key == b"":                            # 引导：空 key 是系统 boot 引导块
        return [(next_key(blk).decode("utf-8","replace"), b"")]   # 最低限度：只取第一条 name（boot）
    return list(iter_tokens(blk))             # 普通块：严格完整解析全部 token

def run_block(start_key=b""):                 # 迭代主循环（对齐 while(1) imp()）：显式栈下钻/重置，不递归
    flush_pending()                          # 运行前 flush 改动（每次运行入口统一保存）
    cur_key = start_key                      # 当前块 key（空 key 引导或指定块）
    vmstate.cur_key = cur_key                # 暴露当前块 key（editor/rerun 定位所在块用，替代 inspect）
    cur_toks = _load_toks(cur_key)           # 加载当前块 token 流
    cur_i = 0                                # 当前块内的 token 位置
    stack = []                                # 下钻返回栈 [(key, toks, i)]（cond/handrun/块引用下钻）
    while True:                               # —— 迭代执行（不递归、不堆积）——
        if cur_i >= len(cur_toks):            # 当前块已走完
            if stack:                         # 有下钻返回栈 → 弹栈回上层继续
                cur_key, cur_toks, cur_i = stack.pop()   # 恢复上层块与位置
                continue                      # 继续迭代上层块
            break                             # 栈空 → 全部执行完 → 结束
        name, payload = cur_toks[cur_i]       # 取当前 token（名字 + payload）
        cur_i += 1                            # 默认推进位置（插件 run_next 的迭代语义）
        try:
            src = load_src(name.encode())     # 尝试加载该 token 的插件源码
        except OSError:                       # 无插件 → 该 token 是块引用，下钻其块
            stack.append((cur_key, cur_toks, cur_i))   # 压栈当前块与位置（执行完返回）
            cur_key = name.encode()           # 切换到被引用的块 key
            vmstate.cur_key = cur_key         # 同步暴露当前块 key
            cur_toks = _load_toks(cur_key)    # 加载目标块
            cur_i = 0                         # 从目标块开头执行
            continue                          # 继续迭代（下钻）
        def run_next():                       # 注入给插件的接棒函数：位置已推进（cur_i += 1）
            pass                              # 无需操作——迭代主循环已自动推进
        def run_block(k):                     # 注入给插件的下钻/重跑函数（迭代，不递归）
            nonlocal cur_key, cur_toks, cur_i # 声明修改外层主循环变量
            if k == cur_key:                  # 目标是当前块（rerun 重跑）
                cur_i = 0                     # 重置位置 → 从块头重跑（不压栈）
            else:                             # 目标是其他块（cond/handrun/运行按钮下钻）
                stack.append((cur_key, cur_toks, cur_i))   # 压栈当前块（执行完返回）
                cur_key = k                   # 切换到目标块
                vmstate.cur_key = cur_key     # 同步暴露当前块 key
                cur_toks = _load_toks(k)      # 加载目标块
                cur_i = 0                     # 从目标块开头执行
        try:
            exec(src, {"payload": payload, "run_next": run_next,
                       "run_block": run_block})   # 注入 payload/run_next/run_block 执行插件顶层
        except SystemExit:                    # 正常结束信号（editor 窗口关闭 / ret_int 结束）
            flush_pending()                   # 结束前保存所有编辑改动
            break                             # 退出主循环 → run_block 返回 → vm 结束
