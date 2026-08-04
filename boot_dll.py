# boot_dll.py —— 启动引导（由 boot_dll.c 简化为纯 Python）
# 逻辑：生成/读取机器 id -> 首次上传引导块 -> 取 key -> 按 sha256 加载 dll 并运行
import ctypes, hashlib, os, socket, struct, time

HOST, PORT = "127.0.0.1", 8000
ID_FILE = "id.bin"

def recv_all(s, n):                          # 精确读满 n 字节
    data = b""
    while len(data) < n:
        chunk = s.recv(n - len(data))
        if not chunk: raise ConnectionError("连接被关闭")
        data += chunk
    return data

def upload(key, data):                       # 服务端 op=3：上传数据
    with socket.create_connection((HOST, PORT)) as s:
        s.sendall(b"\x03" + struct.pack("<I", len(key)) + key +
                  struct.pack("<I", len(data)) + data)
        return struct.unpack("<I", recv_all(s, 4))[0]

def fetch(key):                              # 服务端 op=2：按 key 取数据
    with socket.create_connection((HOST, PORT)) as s:
        s.sendall(b"\x02" + struct.pack("<I", len(key)) + key)
        return recv_all(s, struct.unpack("<I", recv_all(s, 4))[0])

def get_id():
    if os.path.exists(ID_FILE):              # 已有 id 直接用
        return open(ID_FILE, "rb").read()
    new_id = os.urandom(32)                  # 首次运行：生成 id 并保存
    open(ID_FILE, "wb").write(new_id)
    # 初始引导块，字节与原 C 版完全一致：[6]editor[0][5]rerun[0][0]
    block = (bytes([6, 0, 0, 0]) + b"editor" + bytes([0, 0, 0, 0]) +
             bytes([5, 0, 0, 0]) + b"rerun" + bytes([0, 0, 0, 0]) +
             bytes([0, 0, 0, 0]))
    upload(new_id, block)
    return new_id

def load_run(key):                           # key 的 sha256 十六进制就是 dll 文件名
    return ctypes.WinDLL(hashlib.sha256(key).hexdigest() + ".dll").run

def run():
    key = get_id()
    while True:
        try:
            p = fetch(key)
            key = p[4 : 4 + struct.unpack("<I", p[:4])[0]]  # 前4字节是 key 长度
            f = load_run(key)
            break
        except Exception:
            time.sleep(1)                    # 没数据/没 dll 就等一会再试
    while True:
        f()

if __name__ == "__main__":
    run()
