# app.py —— Simply Token 节点图编辑器（峰值版，参考 JUST editor.py）
# 多节点 Canvas 图 + 缩放/平移 + SVG 图标（复用 JUST icons/*.svg 路径）
# + 网络节点/服务器查看器（默认打开 零data=空key）+ 编辑大提升（按Y排序、投票确认保存、自动刷新）
import copy, json, math, os, random, re, struct, tkinter as tk
from tkinter import simpledialog, scrolledtext
import boot_dll

# ---------- 块编解码（与旧版兼容） ----------
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

# ---------- SVG path 解析（支持 JUST 图标用到的 M/L/H/V/Z） ----------
def parse_path(d):
    toks = re.findall(r"[MLHVZmlhvz]|-?\d*\.?\d+(?:[eE][-+]?\d+)?", d)
    subs, pts, i = [], [], 0
    def num():
        nonlocal i
        v = float(toks[i]); i += 1; return v
    while i < len(toks):
        t = toks[i]; i += 1
        if t in "Mm":
            x, y = num(), num()
            if t == "m" and pts: x += pts[-1][0]; y += pts[-1][1]
            pts = [(x, y)]
        elif t in "Ll":
            x, y = num(), num()
            if t == "l" and pts: x += pts[-1][0]; y += pts[-1][1]
            pts.append((x, y))
        elif t in "Hh":
            x = num()
            if t == "h" and pts: x += pts[-1][0]
            pts.append((x, pts[-1][1]))
        elif t in "Vv":
            y = num()
            if t == "v" and pts: y += pts[-1][1]
            pts.append((pts[-1][0], y))
        elif t in "Zz" and pts:
            subs.append((pts, True)); pts = []
    if pts: subs.append((pts, False))
    return subs

# SVG 图标：JUST icons/*.svg 的 path 数据（viewBox 24x24，描边色即类别色）
ICONS = {
    "varread":   ["M4 12 L16 12 M12 8 L16 12 L12 16 M18 6 L18 18"],
    "varwrite":  ["M8 12 L20 12 M12 8 L8 12 L12 16 M4 6 L4 18"],
    "varset":    ["M8 8 L16 8 L16 16 L8 16 Z M12 5 L12 8 M12 16 L12 19"],
    "cond":      ["M12 3 L21 12 L12 21 L3 12 Z"],
    "condreexec":["M12 3 L21 12 L12 21 L3 12 Z M12 8 L12 12 L15 12"],
    "runbyhand": ["M8 5 L8 19 L18 12 Z"],
    "net":       ["M12 3 L18.36 5.36 L21 12 L18.36 18.64 L12 21 L5.64 18.64 L3 12 L5.64 5.36 Z",
                  "M3 12 H21 M12 3 L12 21 M12 5 L18.5 7.1 L21.3 12 L18.5 16.9 L12 19 L5.5 16.9 L2.7 12 L5.5 7.1 Z"],
    "label":     ["M6 3 V21 M6 3 H17 L13 7 L17 11 H6 Z"],
    "end":       ["M9 9 H15 V15 H9 Z"],
}
def icon_of(name):
    if name == "net": return "net", "#f7768e"
    if name == "end": return "end", "#ff9e64"
    if name == "read": return "varread", "#c8e0a0"
    if name == "set": return "varset", "#e8c878"
    if name in ("int", "inc"): return "varwrite", "#c8e0a0"
    if name == "ifz": return "cond", "#d080e0"
    if name in ("jmp", "nop"): return "condreexec", "#e090d0"
    if name in ("print", "input"): return "runbyhand", "#80c8f0"
    if name in ("add", "sub", "mul", "div", "rand", "eq", "gt", "lt"): return "varwrite", "#9ece6a"
    return "label", "#73daca"

# ---------- 迷你 VM（值栈 + 变量表，input 可注入） ----------
class VM:
    def __init__(self, root=None, out=print):
        self.root, self.out = root, out
        self.reset()
    def reset(self):
        self.vars, self.stack, self.pc, self.steps = {}, [], 0, 0
        self._inject = None
    def pop(self):
        return self.stack.pop() if self.stack else 0
    def jump(self, target, tokens):
        for i, (n, _) in enumerate(tokens):
            if n == target:
                self.pc = i; return
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
            if self._inject is not None:
                try: val = next(self._inject)
                except StopIteration: val = 0
            else:
                val = simpledialog.askinteger("输入", "请输入数字", parent=self.root)
                val = val if val is not None else 0
            self.stack.append(val)
        elif name == "ifz":
            if self.pop() == 0: self.jump(data, tokens)
        elif name == "jmp":   self.jump(data, tokens)
        elif name == "end":   self.pc = len(tokens)
        elif name == "nop":   pass

# ---------- 节点图编辑器 ----------
BG, PANEL, NODE, TEXT, DIM, EDGE, SEL, GRID = (
    "#0f1218", "#161c29", "#1c2436", "#e8eaf0", "#8fa3c8", "#4f8cff", "#4f8cff", "#232c42")
NW, NH, STATE = 200, 64, "app_state.json"

class App:
    def __init__(self, root):
        self.root = root
        root.title("Simply Token 节点图编辑器")
        root.geometry("1280x780")
        self.nodes, self.sel = [], None
        self.key = b""
        self.zoom, self.ox, self.oy = 1.0, 60, 40
        self.undo_stack, self.pan = [], None
        self.dirty = False
        self.vm = VM(root, self.log)
        self.build_ui()
        self.load()
        self.refresh_viewer()
        self.after_loop()

    # ---------- 界面 ----------
    def build_ui(self):
        self.root.configure(bg=PANEL)
        bar = tk.Frame(self.root, bg=PANEL); bar.pack(fill="x")
        def btn(t, c, ghost=False):
            b = tk.Button(bar, text=t, command=c, bg=("#26314d" if ghost else "#2f6fdd"),
                          fg="#fff", relief="flat", activebackground="#3f7fee", padx=9)
            b.pack(side="left", padx=2, pady=3); return b
        btn("保存到服务器", self.save); btn("加载", self.load); btn("运行", self.run)
        btn("猜数字", self.load_template, ghost=True); btn("自动布局", self.auto_layout, ghost=True)
        btn("撤销", self.undo, ghost=True)
        btn("放大", lambda: self.zoom_at(1.25, self.c.winfo_width()/2, self.c.winfo_height()/2), ghost=True)
        btn("缩小", lambda: self.zoom_at(0.8, self.c.winfo_width()/2, self.c.winfo_height()/2), ghost=True)
        btn("适应", self.fit, ghost=True)
        self.status = tk.Label(bar, text="", bg=PANEL, fg="#7fd6a0"); self.status.pack(side="right", padx=8)

        main = tk.Frame(self.root, bg=PANEL); main.pack(fill="both", expand=True)
        side = tk.Frame(main, bg="#131926", width=250); side.pack(side="left", fill="y")
        side.pack_propagate(False)
        tk.Label(side, text="服务器 data（双击添加）", bg="#1a2233", fg="#b9c7e4",
                 font=("Microsoft YaHei UI", 9, "bold")).pack(fill="x")
        self.viewer = tk.Listbox(side, bg="#0f1420", fg=TEXT, selectbackground=SEL,
                                 selectforeground="#0b0b12", font=("Consolas", 9),
                                 activestyle="none", borderwidth=0, highlightthickness=0)
        self.viewer.pack(fill="both", expand=True, padx=4, pady=4)
        self.viewer.bind("<Double-Button-1>", self.viewer_add)
        tk.Button(side, text="刷新查看器", command=self.refresh_viewer, bg="#26314d", fg="#fff",
                  relief="flat").pack(fill="x", padx=4, pady=(0, 4))
        self.vstatus = tk.Label(side, text="", bg="#131926", fg="#8fa3c8",
                                font=("Microsoft YaHei UI", 8)); self.vstatus.pack(fill="x", padx=4, pady=2)

        self.c = tk.Canvas(main, bg=BG, highlightthickness=0)
        self.c.pack(fill="both", expand=True)
        self.c.bind("<Button-1>", self.on_lpress)
        self.c.bind("<B1-Motion>", self.on_move)
        self.c.bind("<ButtonRelease-1>", self.on_lrelease)
        self.c.bind("<Button-2>", self.on_pan_start)
        self.c.bind("<B2-Motion>", self.on_pan)
        self.c.bind("<Button-3>", self.on_rpress)
        self.c.bind("<B3-Motion>", self.on_rpan)
        self.c.bind("<ButtonRelease-3>", self.on_rrelease)
        self.c.bind("<MouseWheel>", self.on_wheel)
        self.c.bind("<Double-1>", self.on_double)
        self.root.bind("<Delete>", lambda e: self.del_node())
        self.root.bind("<Control-z>", lambda e: self.undo())
        self.root.bind("<Control-s>", lambda e: self.save())
        self.root.bind("<Control-r>", lambda e: self.run())
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

        self.out = scrolledtext.ScrolledText(self.root, height=7, bg="#0d0f16", fg="#9ece6a",
                                             insertbackground="#9ece6a", font=("Consolas", 10))
        self.out.pack(fill="x")

    def log(self, s):
        self.out.insert("end", s + "\n"); self.out.see("end")

    # ---------- 视图变换（缩放/平移） ----------
    def W2S(self, x, y): return x * self.zoom + self.ox, y * self.zoom + self.oy
    def S2W(self, x, y): return (x - self.ox) / self.zoom, (y - self.oy) / self.zoom
    def zoom_at(self, f, sx, sy):
        wx, wy = self.S2W(sx, sy)
        self.zoom = max(0.2, min(3.0, self.zoom * f))
        self.ox, self.oy = sx - wx * self.zoom, sy - wy * self.zoom
        self.redraw()
    def on_wheel(self, e):
        self.zoom_at(1.1 if e.delta > 0 else 1 / 1.1, e.x, e.y)
    def fit(self):
        if not self.nodes:
            self.zoom, self.ox, self.oy = 1.0, 60, 40; self.redraw(); return
        xs = [n["x"] for n in self.nodes]; ys = [n["y"] for n in self.nodes]
        w, h = self.c.winfo_width(), self.c.winfo_height()
        if w < 10: w, h = 900, 500
        z = min((w - 80) / (max(xs) - min(xs) + NW), (h - 80) / (max(ys) - min(ys) + NH), 1.5)
        z = max(0.2, z)
        self.zoom = z
        self.ox = w / 2 - z * (min(xs) + max(xs)) / 2
        self.oy = h / 2 - z * (min(ys) + max(ys)) / 2
        self.redraw()
    def on_pan_start(self, e):
        self.pan = (e.x, e.y)
    def on_pan(self, e):
        if self.pan:
            self.ox += e.x - self.pan[0]; self.oy += e.y - self.pan[1]
            self.pan = (e.x, e.y)
            self.redraw()
    def on_rpress(self, e):
        self.pan = (e.x, e.y); self._rmoved = 0
    def on_rpan(self, e):
        self._rmoved = max(self._rmoved, abs(e.x - self.pan[0]) + abs(e.y - self.pan[1]))
        self.on_pan(e)
    def on_rrelease(self, e):
        if self._rmoved < 6: self.show_menu(e)

    # ---------- 节点交互 ----------
    def node_at(self, wx, wy):
        for n in reversed(self.nodes):
            if abs(wx - n["x"]) <= NW / 2 and abs(wy - n["y"]) <= NH / 2:
                return n
        return None
    def on_lpress(self, e):
        wx, wy = self.S2W(e.x, e.y)
        n = self.node_at(wx, wy)
        if n:
            self.sel = n; self._drag = (wx - n["x"], wy - n["y"])
        else:
            self.sel = None; self._drag = None
        self.redraw()
    def on_move(self, e):
        if self._drag:
            wx, wy = self.S2W(e.x, e.y)
            self.sel["x"], self.sel["y"] = round(wx - self._drag[0]), round(wy - self._drag[1])
            self.redraw()
    def on_lrelease(self, e):
        self._drag = None
    def on_double(self, e):
        n = self.node_at(*self.S2W(e.x, e.y))
        if n: self.edit_node(n)
    def snapshot(self):
        self.undo_stack.append(copy.deepcopy(self.nodes))
        if len(self.undo_stack) > 60: self.undo_stack.pop(0)
    def undo(self):
        if self.undo_stack:
            self.nodes = self.undo_stack.pop()
            self.sel = None; self.dirty = True
            self.redraw(); self.status.config(text="已撤销")
    def add_node(self, name, data=""):
        self.snapshot()
        x, y = self.S2W(self.c.winfo_width() / 2, self.c.winfo_height() / 2)
        n = len(self.nodes)
        self.nodes.append({"name": name, "data": data,
                           "x": round(x) + (n % 5) * 30, "y": round(y) + (n % 4) * 26})
        self.sel = self.nodes[-1]; self.dirty = True
        self.redraw()
    def del_node(self):
        if self.sel is None: return
        self.snapshot(); self.nodes.remove(self.sel)
        self.sel = None; self.dirty = True
        self.redraw()
    def dup_node(self):
        if self.sel is None: return
        self.snapshot()
        c = copy.deepcopy(self.sel); c["y"] += NH + 20
        self.nodes.append(c); self.sel = c; self.dirty = True
        self.redraw()

    # 执行/保存顺序 = 按 Y 排序（JUST 同款），连线自动重建
    def ordered(self):
        return sorted(self.nodes, key=lambda n: (n["y"], self.nodes.index(n)))

    # ---------- 右键菜单 ----------
    def show_menu(self, e):
        wx, wy = self.S2W(e.x, e.y)
        n = self.node_at(wx, wy)
        m = tk.Menu(self.root, tearoff=0, bg=PANEL, fg=TEXT, activebackground=SEL)
        if n:
            m.add_command(label="编辑…", command=lambda: self.edit_node(n))
            m.add_command(label="复制", command=self.dup_node)
            m.add_command(label="删除", command=self.del_node)
            if n["name"] == "net":
                m.add_separator()
                m.add_command(label="打开网络节点…", command=lambda: self.net_dialog(n))
            m.add_command(label="运行", command=self.run)
        else:
            self.sel = None; self.redraw()
            def cat(label, names):
                sub = tk.Menu(m, tearoff=0, bg=PANEL, fg=TEXT, activebackground=SEL)
                for nm in names:
                    sub.add_command(label=nm, command=lambda k=nm: self.add_node(k, "零data" if k == "net" else ""))
                m.add_cascade(label=label, menu=sub)
            cat("变量", ["int", "set", "read", "inc"])
            cat("运算", ["add", "sub", "mul", "div", "rand", "eq", "gt", "lt"])
            cat("控制", ["ifz", "jmp", "end", "nop"])
            cat("交互", ["print", "input"])
            cat("标签", ["main", "notwin", "loop", "exit"])
            cat("网络", ["net"])
            m.add_separator()
            m.add_command(label="自动布局", command=self.auto_layout)
            m.add_command(label="载入猜数字示例", command=self.load_template)
        try:
            m.tk_popup(e.x_root, e.y_root)
        finally:
            m.grab_release()

    # ---------- 编辑节点 ----------
    def edit_node(self, node):
        if node["name"] == "net":
            self.net_dialog(node); return
        win = tk.Toplevel(self.root); win.title("编辑节点")
        win.configure(bg=PANEL); win.resizable(False, False)
        tk.Label(win, text="token", bg=PANEL, fg=TEXT).grid(row=0, column=0, padx=6, pady=6)
        e1 = tk.Entry(win, width=14); e1.insert(0, node["name"]); e1.grid(row=0, column=1, padx=6)
        tk.Label(win, text="data", bg=PANEL, fg=TEXT).grid(row=1, column=0, padx=6)
        e2 = tk.Entry(win, width=30); e2.insert(0, node["data"]); e2.grid(row=1, column=1, padx=6)
        def ok():
            self.snapshot()
            node["name"] = e1.get().strip() or "nop"
            node["data"] = e2.get()
            self.dirty = True
            self.redraw(); win.destroy()
        def dele():
            self.snapshot(); self.nodes.remove(node); self.sel = None
            self.dirty = True; self.redraw(); win.destroy()
        tk.Button(win, text="确定", command=ok, bg="#2f6fdd", fg="#fff", relief="flat").grid(row=2, column=0, padx=6, pady=8)
        tk.Button(win, text="删除", command=dele, bg="#5a2a33", fg="#fff", relief="flat").grid(row=2, column=1, sticky="w", padx=6)

    # ---------- 服务器查看器（网络节点，默认开 零data=空key） ----------
    def viewer_groups(self):
        keys = [b""]
        if self.key: keys.append(self.key)
        for n in self.nodes:
            d = n["data"].encode("utf-8")
            if d and d not in keys: keys.append(d)
        groups = []
        for k in keys:
            try:
                toks = decode(boot_dll.fetch(k)) if k else []
            except Exception:
                toks = []
            groups.append((k, toks))
        return groups

    def refresh_viewer(self):
        self.viewer.delete(0, "end")
        groups = self.viewer_groups()
        for k, toks in groups:
            label = "<空 key> 零data" if not k else k.decode("utf-8", "replace")[:20]
            self.viewer.insert("end", "\u25b8 " + label + "（" + str(len(toks)) + "）")
            for nm, dt in toks:
                self.viewer.insert("end", "   " + nm + ("  |  " + dt if dt else ""))
        self.vstatus.config(text="%d 组 key / %d token" % (len(groups), sum(len(t) for _, t in groups)))

    def viewer_add(self, e):
        i = self.viewer.nearest(e.y)
        if i < 0: return
        txt = self.viewer.get(i)
        if " | " in txt:
            tok, dat = txt.strip().split(" | ", 1)
            self.add_node(tok, dat)
        elif txt.startswith("\u25b8"):
            self.status.config(text="双击数据行添加节点")

    def net_dialog(self, node):
        win = tk.Toplevel(self.root); win.title("网络节点 - 查看服务器")
        win.configure(bg=PANEL); win.geometry("580x430")
        top = tk.Frame(win, bg=PANEL); top.pack(fill="x", padx=8, pady=6)
        tk.Label(top, text="key:", bg=PANEL, fg=TEXT).pack(side="left")
        ent = tk.Entry(top, width=42); ent.insert(0, node["data"] or ""); ent.pack(side="left", padx=4)
        lb = tk.Listbox(win, bg="#0f1420", fg=TEXT, selectbackground=SEL, font=("Consolas", 10))
        lb.pack(fill="both", expand=True, padx=8, pady=4)
        status = tk.Label(win, text="", bg=PANEL, fg=DIM); status.pack(fill="x", padx=8)
        bot = tk.Frame(win, bg=PANEL); bot.pack(fill="x", padx=8, pady=6)
        def refresh():
            lb.delete(0, "end")
            k = ent.get().strip().encode("utf-8")
            try:
                toks = decode(boot_dll.fetch(k)) if k else []
                if not toks: lb.insert("end", "(空块)")
                for nm, dt in toks:
                    lb.insert("end", nm + ("  |  " + dt if dt else ""))
                status.config(text="已取回 %d 个 token" % len(toks))
            except Exception:
                lb.insert("end", "(服务器无此 key 的数据)")
                status.config(text="key='%s' 无数据" % ent.get().strip())
        def browse():
            lb.delete(0, "end")
            try:
                keys = boot_dll.list_keys()
                if not keys: lb.insert("end", "(服务器为空)")
                for k, c in keys:
                    lb.insert("end", "[%d条] %s" % (c, k.decode("utf-8", "replace") or "<空 key>"))
                status.config(text="共 %d 个 key" % len(keys))
            except Exception as ex:
                status.config(text="浏览失败: %s" % ex)
        def use_selected():
            s = lb.curselection()
            if not s: return
            txt = lb.get(s[0])
            if " | " in txt: txt = txt.split(" | ", 1)[0]
            if txt.startswith("[") and "条] " in txt: txt = txt.split("] ", 1)[1]
            ent.delete(0, "end"); ent.insert(0, txt)
            refresh()
        def load_into_editor():
            k = ent.get().strip().encode("utf-8")
            try:
                toks = decode(boot_dll.fetch(k)) if k else []
                if not toks:
                    status.config(text="空块，无法载入"); return
                self.snapshot()
                x, y = self.S2W(self.c.winfo_width() / 2, self.c.winfo_height() / 2)
                for i, (nm, dt) in enumerate(toks):
                    self.nodes.append({"name": nm, "data": dt,
                                       "x": round(x) + (i % 6) * 30, "y": round(y) + (i // 6) * 30})
                node["data"] = ent.get().strip()
                self.dirty = True; self.redraw()
                status.config(text="已载入 %d 个 token 到编辑器" % len(toks))
            except Exception:
                status.config(text="载入失败：服务器无此 key")
        def setkey():
            node["data"] = ent.get().strip(); status.config(text="已设为节点 key")
        for t, c in [("刷新", refresh), ("浏览服务器", browse), ("使用选中", use_selected),
                     ("载入编辑器", load_into_editor), ("设为节点key", setkey), ("关闭", win.destroy)]:
            tk.Button(bot, text=t, command=c, bg="#26314d", fg="#fff", relief="flat").pack(side="left", padx=3)

    # ---------- 布局 ----------
    def auto_layout(self):
        if not self.nodes: return
        self.snapshot()
        w = self.c.winfo_width() or 900
        cols = max(1, int((w - 80) / (NW + 40)))
        for i, n in enumerate(self.nodes):
            n["x"] = 40 + (i % cols) * (NW + 40)
            n["y"] = 40 + (i // cols) * (NH + 40)
        self.fit()
        self.status.config(text="已自动布局 %d 个节点" % len(self.nodes))

    def load_template(self):
        self.snapshot()
        self.nodes = []
        for i, (nm, dt) in enumerate(guess_template()):
            self.nodes.append({"name": nm, "data": dt, "x": 40 + (i % 5) * (NW + 40),
                               "y": 40 + (i // 5) * (NH + 40)})
        self.sel = None; self.dirty = True
        self.fit()
        self.status.config(text="已载入猜数字示例（28 节点）")

    # ---------- 服务器存取 ----------
    def save(self):
        if not self.key:
            try: self.key = boot_dll.get_id()
            except Exception as e:
                self.status.config(text="保存失败: " + str(e)); return
        payload = encode([(n["name"], n["data"]) for n in self.ordered()])
        try:
            idx = boot_dll.upload(self.key, payload)
            ok = False
            for _ in range(50):
                try:
                    if boot_dll.fetch(self.key) == payload:
                        ok = True; break
                except Exception:
                    break
                boot_dll.vote(self.key, idx)
            self.dirty = False
            self.save_layout()
            self.status.config(text=("已保存 idx=%d（服务器已确认）" % idx) if ok else ("已保存 idx=%d，投票中" % idx))
        except Exception as e:
            self.status.config(text="保存失败: " + str(e))

    def save_layout(self):
        try:
            json.dump({"nodes": self.nodes}, open(STATE, "w", encoding="utf-8"), ensure_ascii=False)
        except Exception:
            pass

    def load(self):
        try:
            self.key = boot_dll.get_id()
        except Exception as e:
            self.status.config(text="无法获取 id: " + str(e)); return
        try:
            toks = decode(boot_dll.fetch(self.key))
        except Exception:
            toks = []
        if toks == [("editor", ""), ("rerun", "")]:
            toks = guess_template()
            self.nodes = []
            for i, (nm, dt) in enumerate(toks):
                self.nodes.append({"name": nm, "data": dt, "x": 40 + (i % 5) * (NW + 40),
                                   "y": 40 + (i // 5) * (NH + 40)})
            self.save()
            return
        cur = [(n["name"], n["data"]) for n in self.nodes]
        if cur == toks:
            self.redraw()
            return
        saved = None
        try:
            saved = json.load(open(STATE, encoding="utf-8"))["nodes"]
        except Exception:
            saved = None
        seq = [(n["name"], n["data"]) for n in (saved or [])]
        if saved and seq == toks:
            self.nodes = saved
        else:
            self.nodes = []
            for i, (nm, dt) in enumerate(toks):
                self.nodes.append({"name": nm, "data": dt, "x": 40 + (i % 5) * (NW + 40),
                                   "y": 40 + (i // 5) * (NH + 40)})
        self.sel = None; self.dirty = False
        self.redraw()
        self.status.config(text="已加载，共 %d 个节点" % len(self.nodes))

    def after_loop(self):
        if not self.dirty:
            self.load(); self.refresh_viewer()
        self.root.after(3000, self.after_loop)

    def run(self):
        self.out.delete("1.0", "end")
        toks = [(n["name"], n["data"]) for n in self.ordered()]
        self.log("--- 运行 %d 个节点（按 Y 排序）---" % len(toks))
        self.vm.run(toks)
        self.status.config(text="运行结束，共 %d 步" % self.vm.steps)

    def on_close(self):
        self.save_layout()
        self.root.destroy()

    # ---------- 绘制 ----------
    def rrect(self, x1, y1, x2, y2, r=12):
        pts = []
        def arc(cx, cy, a0, a1):
            for i in range(5):
                a = math.radians(a0 + (a1 - a0) * i / 4)
                pts.append((cx + r * math.cos(a), cy - r * math.sin(a)))
        arc(x1 + r, y1 + r, 180, 270); arc(x2 - r, y1 + r, 270, 360)
        arc(x2 - r, y2 - r, 0, 90); arc(x1 + r, y2 - r, 90, 180)
        return pts

    def draw_icon(self, icon, color, cx, cy):
        for d in ICONS[icon]:
            for pts, closed in parse_path(d):
                p = [(cx + (px - 12) * 0.85, cy + (py - 12) * 0.85) for px, py in pts]
                self.c.create_line(p, fill=color, width=2, capstyle="round", joinstyle="round")

    def redraw(self):
        self.c.delete("all")
        w, h = self.c.winfo_width(), self.c.winfo_height()
        x0, y0 = self.S2W(0, 0); x1, y1 = self.S2W(w, h)
        g = 50
        gx = int(x0 // g) * g
        while gx <= x1:
            sx, _ = self.W2S(gx, 0); self.c.create_line(sx, 0, sx, h, fill=GRID); gx += g
        gy = int(y0 // g) * g
        while gy <= y1:
            _, sy = self.W2S(0, gy); self.c.create_line(0, sy, w, sy, fill=GRID); gy += g
        order = self.ordered()
        for i in range(len(order) - 1):
            a, b = order[i], order[i + 1]
            x1_, y1_ = self.W2S(a["x"] + NW / 2, a["y"])
            x2_, y2_ = self.W2S(b["x"] - NW / 2, b["y"])
            self.c.create_line(x1_, y1_, x2_, y2_, fill=EDGE, width=2)
            ang = math.atan2(y2_ - y1_, x2_ - x1_)
            for k in (-1, 1):
                ax = x2_ + 9 * math.cos(ang + k * 2.6)
                ay = y2_ + 9 * math.sin(ang + k * 2.6)
                self.c.create_line(x2_, y2_, ax, ay, fill=EDGE, width=2)
        for n in self.nodes:
            self.draw_node(n)
        if self.dirty:
            self.status.config(text="%d 节点 | 缩放 %.2fx | 未保存" % (len(self.nodes), self.zoom))
        else:
            self.status.config(text="%d 节点 | 缩放 %.2fx" % (len(self.nodes), self.zoom))

    def draw_node(self, n):
        x1, y1 = self.W2S(n["x"] - NW / 2, n["y"] - NH / 2)
        x2, y2 = self.W2S(n["x"] + NW / 2, n["y"] + NH / 2)
        if self.zoom < 0.35:
            self.c.create_rectangle(x1, y1, x2, y2, fill=NODE, outline=GRID)
            return
        poly = self.rrect(x1, y1, x2, y2)
        self.c.create_polygon(poly, fill=NODE, outline=(SEL if n is self.sel else "#33405e"), width=2)
        icon, color = icon_of(n["name"])
        cx, cy = self.W2S(n["x"] - NW / 2 + 28, n["y"])
        self.draw_icon(icon, color, cx, cy)
        tx, ty = self.W2S(n["x"] - NW / 2 + 48, n["y"] - 8)
        self.c.create_text(tx, ty, anchor="w", text=n["name"], fill=TEXT, font=("Microsoft YaHei UI", 10, "bold"))
        dx, dy = self.W2S(n["x"] - NW / 2 + 48, n["y"] + 14)
        dt = n["data"] if n["data"] else ("零data" if n["name"] == "net" else "(空)")
        if len(dt) > 16: dt = dt[:15] + "…"
        self.c.create_text(dx, dy, anchor="w", text=dt, fill=DIM, font=("Microsoft YaHei UI", 8))

if __name__ == "__main__":
    root = tk.Tk()
    App(root)
    root.mainloop()
