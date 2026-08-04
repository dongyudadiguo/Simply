# boot.py —— 最简启动器（自包含，无需其他文件）
# 取 id -> 从服务器拉当前块 -> 解码 token -> 控制台执行
# 用法: python boot.py   （input token 在控制台等输入，猜数字直接玩）
import os, random, socket, struct

HOST, PORT = "127.0.0.1", 8000
ID_FILE = "id.bin"

def recv_all(s, n):
    data = b""
    while len(data) < n:
        chunk = s.recv(n - len(data))
        if not chunk: raise ConnectionError("连接被关闭")
        data += chunk
    return data

def upload(key, data):                       # op=3 上传
    with socket.create_connection((HOST, PORT), timeout=3) as s:
        s.sendall(b"\x03" + struct.pack("<I", len(key)) + key +
                  struct.pack("<I", len(data)) + data)
        return struct.unpack("<I", recv_all(s, 4))[0]

def fetch(key):                              # op=2 取数据（票数最高）
    with socket.create_connection((HOST, PORT), timeout=3) as s:
        s.sendall(b"\x02" + struct.pack("<I", len(key)) + key)
        return recv_all(s, struct.unpack("<I", recv_all(s, 4))[0])

def get_id():
    if os.path.exists(ID_FILE):
        return open(ID_FILE, "rb").read()
    new_id = os.urandom(32)
    open(ID_FILE, "wb").write(new_id)
    # 首次运行：上传引导块 [editor][rerun]
    block = (bytes([6, 0, 0, 0]) + b"editor" + bytes([0, 0, 0, 0]) +
             bytes([5, 0, 0, 0]) + b"rerun" + bytes([0, 0, 0, 0]) +
             bytes([0, 0, 0, 0]))
    upload(new_id, block)
    return new_id

def decode(blk):
    tokens, i = [], 0
    while i + 4 <= len(blk):
        n = struct.unpack("<I", blk[i:i + 4])[0]; i += 4
        if n == 0: break
        name = blk[i:i + n].decode("utf-8", "replace"); i += n
        if i + 4 > len(blk): break
        d = struct.unpack("<I", blk[i:i + 4])[0]; i += 4
        data = blk[i:i + d].decode("utf-8", "replace"); i += d
        tokens.append((name, data))
    return tokens

# ---------- 迷你 VM（值栈 + 变量表，控制台输入） ----------
class VM:
    def __init__(self):
        self.vars, self.stack, self.pc, self.steps = {}, [], 0, 0
    def pop(self):
        return self.stack.pop() if self.stack else 0
    def jump(self, target, tokens):
        for i, (n, _) in enumerate(tokens):
            if n == target:
                self.pc = i; return
        print("(跳转目标不存在: " + target + ")")
    def run(self, tokens, max_steps=1000):
        while self.pc < len(tokens) and self.steps < max_steps:
            self.steps += 1
            name, data = tokens[self.pc]
            self.pc += 1
            self.exec(name, data, tokens)
        if self.steps >= max_steps:
            print("(达到步数上限，已停止)")
    def exec(self, name, data, tokens):
        v = self.vars
        if   name == "int":   v.setdefault(data, 0)
        elif name == "set":   v[data] = self.pop()
        elif name == "read":  self.stack.append(v.get(data, 0))
        elif name == "inc":   v[data] = v.get(data, 0) + 1
        elif name == "add":   a, b = self.pop(), self.pop(); self.stack.append(b + a)
        elif name == "sub":   a, b = self.pop(), self.pop(); self.stack.append(b - a)
        elif name == "mul":   a, b = self.pop(), self.pop(); self.stack.append(b * a)
        elif name == "div":   a, b = self.pop(), self.pop(); self.stack.append(b // a if a else 0)
        elif name == "rand":  self.stack.append(random.randint(1, int(data or 100)))
        elif name == "eq":    a, b = self.pop(), self.pop(); self.stack.append(1 if b == a else 0)
        elif name == "gt":    a, b = self.pop(), self.pop(); self.stack.append(1 if b > a else 0)
        elif name == "lt":    a, b = self.pop(), self.pop(); self.stack.append(1 if b < a else 0)
        elif name == "print":
            print(data if data else str(self.pop()))
        elif name == "input":
            try:
                self.stack.append(int(input("> ")))
            except Exception:
                self.stack.append(0)
        elif name == "ifz":
            if self.pop() == 0: self.jump(data, tokens)
        elif name == "jmp":   self.jump(data, tokens)
        elif name == "end":   self.pc = len(tokens)
        # 其他名字 = 标签/占位，什么都不做

def main():
    key = get_id()
    blk = fetch(key)
    tokens = decode(blk)
    print("当前块 %d tokens，开始执行" % len(tokens))
    VM().run(tokens)

if __name__ == "__main__":
    main()
