# vm.py —— 虚拟机客户端（由 vm.c 简化为纯 Python）
# 逻辑：连本地服务器取 key -> 按 key 的 sha256 找本地 dll -> LoadLibrary 调 run
import ctypes, hashlib, socket, struct, time

HOST, PORT = "127.0.0.1", 8000

def recv_all(s, n):                          # 精确读满 n 字节
    data = b""
    while len(data) < n:
        chunk = s.recv(n - len(data))
        if not chunk: raise ConnectionError("连接被关闭")
        data += chunk
    return data

def fetch(key):                              # 服务端 op=2：按 key 取数据
    with socket.create_connection((HOST, PORT)) as s:
        s.sendall(b"\x02" + struct.pack("<I", len(key)) + key)
        return recv_all(s, struct.unpack("<I", recv_all(s, 4))[0])

def load_run(key):                           # key 的 sha256 十六进制就是 dll 文件名
    dll = ctypes.WinDLL(hashlib.sha256(key).hexdigest() + ".dll")
    return dll.run

def main():
    key = b""
    while True:
        try:
            p = fetch(key)
            key = p[4 : 4 + struct.unpack("<I", p[:4])[0]]  # 前4字节是 key 长度
            run = load_run(key)
            break
        except Exception:
            time.sleep(1)                    # 没数据/没 dll 就等一会再试
    while True:
        run()

if __name__ == "__main__":
    main()
