# app.py —— Token 图形编辑器 + 迷你 VM（tkinter 最简版）
# 编辑/保存/运行 token 块；内置 mod：
#   变量: int / set / read / inc
#   运算: add / sub / mul / div / rand / eq / gt / lt
#   控制: ifz / jmp / end / nop
#   交互: print / input
import random, struct, tkinter as tk
from tkinter import simpledialog, scrolledtext
import boot_dll

# ---------- 块编解码： [4B名长][名][4B数据长][数据] ... [0] ----------
def encode(tokens):
    out = b""
    for name, data in tokens:
        nb, db = name.encode(), data.encode()
        out += struct.pack("<I", len(nb)) + nb + struct.pack("<I", len(db)) + db
    return out + b"\x00\x00\x00\x00"

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

# ---------- 猜数字示例块（可直接编辑） ----------
def guess_template():
    return [
        ("int", "target"), ("int", "guess"), ("int", "tries"),
        ("rand", "100"), ("set", "target"),
        ("print", "已生成 1-100 的随机数，开始猜吧！"),
        ("main", ""),
        ("inc", "tries"), ("input", ""), ("set", "guess"),
        ("read", "guess"), ("read", "target"), ("eq", ""), ("ifz", "notwin"),
        ("print", "猜中了！用了 "), ("read", "tries"), ("print", ""), ("end", ""),
        ("notwin", ""),
        ("read", "guess"), ("read", "target"), ("gt", ""), ("ifz", "lower"),
        ("print", "大了"), ("jmp", "main"),
        ("lower", ""),
        ("print", "小了"), ("jmp", "main"),
    ]

# ---------- 迷你 VM（值栈 + 变量表） ----------
class VM:
    def __init__(self, root=None, out=print):
        self.root, self.out = root, out
        self.reset()

    def reset(self):
        self.vars, self.stack, self.pc, self.steps = {}, [], 0, 0

    def pop(self):
        return self.stack.pop() if self.stack else 0

    def jump(self, target, tokens):
        for i, (n, _) in enumerate(tokens):
            if n == target:
                self.pc = i
                return
        self.out("(跳转目标不存在: " + target + ")")

    def run(self, tokens, max_steps=1000):
        self.reset()
        while self.pc < len(tokens) and self.steps < max_steps:
            self.steps += 1
            name, data = tokens[self.pc]
            self.pc += 1
            self.exec(name, data, tokens)
        if self.steps >= max_steps:
            self.out("(达到步数上限，已停止)")

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
            self.out(data if data else str(self.pop()))
        elif name == "input":
            val = simpledialog.askinteger("输入", "请输入数字", parent=self.root)
            self.stack.append(val if val is not None else 0)
        elif name == "ifz":
            if self.pop() == 0:
                self.jump(data, tokens)
        elif name == "jmp":   self.jump(data, tokens)
        elif name == "end":   self.pc = len(tokens)
        elif name == "nop":   pass
        # 其他名字 = 标签/占位，什么都不做

# ---------- 图形界面 ----------
class App:
    def __init__(self, root):
        self.root = root
        root.title("Token 编辑器 - 猜数字")
        self.tokens = []
        self.id = b""
        self.vm = VM(root, self.log)

        top = tk.Frame(root); top.pack(fill="x", padx=4, pady=2)
        tk.Button(top, text="加载", command=self.load).pack(side="left")
        tk.Button(top, text="保存到服务器", command=self.save).pack(side="left")
        tk.Button(top, text="运行", command=self.run).pack(side="left")
        tk.Button(top, text="猜数字示例", command=self.load_template).pack(side="left")
        self.status = tk.Label(top, text="", fg="#666"); self.status.pack(side="left", padx=8)

        mid = tk.Frame(root); mid.pack(fill="both", expand=True, padx=4)
        self.listbox = tk.Listbox(mid)
        self.listbox.pack(side="left", fill="both", expand=True)
        sb = tk.Scrollbar(mid, command=self.listbox.yview); sb.pack(side="left", fill="y")
        self.listbox.config(yscrollcommand=sb.set)
        self.listbox.bind("<<ListboxSelect>>", self.on_select)

        edit = tk.Frame(root); edit.pack(fill="x", padx=4, pady=2)
        tk.Label(edit, text="token:").pack(side="left")
        self.e_name = tk.Entry(edit, width=12); self.e_name.pack(side="left")
        tk.Label(edit, text="data:").pack(side="left")
        self.e_data = tk.Entry(edit, width=30); self.e_data.pack(side="left")
        tk.Button(edit, text="添加", command=self.add).pack(side="left", padx=2)
        tk.Button(edit, text="更新", command=self.update).pack(side="left", padx=2)
        tk.Button(edit, text="删除", command=self.delete).pack(side="left", padx=2)
        tk.Button(edit, text="上移", command=lambda: self.move(-1)).pack(side="left", padx=2)
        tk.Button(edit, text="下移", command=lambda: self.move(1)).pack(side="left", padx=2)

        self.out = scrolledtext.ScrolledText(root, height=12)
        self.out.pack(fill="both", expand=True, padx=4, pady=4)

        self.load()

    # ---- 界面操作 ----
    def log(self, s):
        self.out.insert("end", s + "\n")
        self.out.see("end")

    def refresh(self):
        self.listbox.delete(0, "end")
        for name, data in self.tokens:
            self.listbox.insert("end", name + ("  |  " + data if data else ""))

    def selected(self):
        sel = self.listbox.curselection()
        return sel[0] if sel else None

    def on_select(self, _e=None):
        i = self.selected()
        if i is not None:
            name, data = self.tokens[i]
            self.e_name.delete(0, "end"); self.e_name.insert(0, name)
            self.e_data.delete(0, "end"); self.e_data.insert(0, data)

    def add(self):
        self.tokens.append((self.e_name.get().strip() or "nop", self.e_data.get()))
        self.refresh()

    def update(self):
        i = self.selected()
        if i is not None:
            self.tokens[i] = (self.e_name.get().strip() or "nop", self.e_data.get())
            self.refresh()

    def delete(self):
        i = self.selected()
        if i is not None:
            self.tokens.pop(i); self.refresh()

    def move(self, d):
        i = self.selected()
        j = i + d
        if i is not None and 0 <= j < len(self.tokens):
            self.tokens[i], self.tokens[j] = self.tokens[j], self.tokens[i]
            self.refresh(); self.listbox.selection_set(j)

    # ---- 服务器 ----
    def load(self):
        try:
            self.id = boot_dll.get_id()
        except Exception as e:
            self.status.config(text="无法获取 id: " + str(e)); return
        try:
            blk = boot_dll.fetch(self.id)
            self.tokens = decode(blk)
        except Exception:
            self.tokens = []
        if self.tokens == [("editor", ""), ("rerun", "")]:
            self.tokens = guess_template()      # 首次运行：直接给猜数字示例
            self.save()
        self.refresh()
        self.status.config(text="已加载，共 %d 个 token" % len(self.tokens))

    def save(self):
        if not self.id:
            try: self.id = boot_dll.get_id()
            except Exception as e:
                self.status.config(text="保存失败: " + str(e)); return
        try:
            idx = boot_dll.upload(self.id, encode(self.tokens))
            votes = boot_dll.vote(self.id, idx)
            self.status.config(text="已保存 idx=%d votes=%d" % (idx, votes))
        except Exception as e:
            self.status.config(text="保存失败: " + str(e))

    def run(self):
        self.out.delete("1.0", "end")
        self.vm.run(self.tokens)
        self.status.config(text="运行结束，共 %d 步" % self.vm.steps)

    def load_template(self):
        self.tokens = guess_template()
        self.refresh()
        self.status.config(text="已载入猜数字示例，可编辑后保存")

if __name__ == "__main__":
    root = tk.Tk()
    App(root)
    root.mainloop()
