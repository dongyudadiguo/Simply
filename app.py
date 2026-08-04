# app.py —— Simply Token 节点图编辑器（峰值版 v3，参考 JUST editor.py + Singularity 自举编辑器）
# 多节点树形图(children/firstchild) + 缩放(平滑)/平移 + SVG 图标(JUST+Singularity 复用)
# + 网络节点/服务器查看器(零data) + 内联编辑 + 投票确认保存 + 自动刷新
import copy, json, math, os, random, re, struct, tkinter as tk
from tkinter import simpledialog, scrolledtext
import boot_dll

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

# SVG 图标：JUST icons/ + Singularity icons/ 的 path 数据（viewBox 24x24，描边色=类别色）
ICONS = {
    "varread":   ["M4 12 L16 12 M12 8 L16 12 L12 16 M18 6 L18 18"],          # #c8e0a0 读变量
    "varwrite":  ["M8 12 L20 12 M12 8 L8 12 L12 16 M4 6 L4 18"],             # #c8e0a0 写变量
    "varset":    ["M12 3 L12 3 M8 8 L16 8 L16 16 L8 16 Z M12 12 L12 12"],    # #e8c878 设置
    "cond":      ["M12 3 L21 12 L12 21 L3 12 Z"],                            # #d080e0 条件/比较
    "jump":      ["M5 12 L15 12 M11 8 L15 12 L11 16 M18 6 L18 18"],          # #5ec8e8 跳转
    "exec":      ["M8 5 L8 19 L19 12 Z"],                                    # #5ec8e8 执行/输出
    "key":       ["M3 8 L21 8 L21 16 L3 16 Z"],                              # #e0a050 输入
    "const":     ["M7 7 L17 7 L17 17 L7 17 Z"],                              # #7fb8d8 常量/整数
    "f32":       ["M6 16 L10 8 L14 16 M8 13 L12 13"],                        # #7fb8d8 数字
    "add":       ["M12 5 L12 19 M5 12 L19 12"],                              # #5ec8e8 +
    "sub":       ["M5 12 L19 12"],                                           # #5ec8e8 -
    "mul":       ["M6 6 L18 18 M18 6 L6 18"],                                # #5ec8e8 x
    "div":       ["M6 18 L18 6 M12 5 L12 5 M12 19 L12 19"],                  # #5ec8e8 /
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
    if name in ("int",): return "const", "#7fb8d8"
    if name == "inc": return "add", "#5ec8e8"
    if name in ("rand", "div"): return "div", "#5ec8e8"
    if name == "add": return "add", "#5ec8e8"
    if name == "sub": return "sub", "#5ec8e8"
    if name == "mul": return "mul", "#5ec8e8"
    if name in ("eq", "gt", "lt", "ifz"): return "cond", "#d080e0"
    if name == "jmp": return "jump", "#5ec8e8"
    if name == "nop": return "add", "#5ec8e8"
    if name == "print": return "exec", "#5ec8e8"
    if name == "input": return "key", "#e0a050"
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
        self.inline = None
        self.view_mode = "graph"
        self.list_btn = None
        self.sel_block = None
        self.vm = VM(root, self.log)
        self.build_ui()
        self.load()
        self.refresh_viewer()
        self.after_loop()

    # ---------- 树形辅助 ----------
    def new_node(self, name, data="", x=0, y=0):
        return {"name": name, "data": data, "x": x, "y": y, "children": [], "collapsed": False}

    def wrap_block(self, title, tokens, x=40, y=40):
        """一个块节点 = 标题 + 多个 token 子节点（Singularity 风格）"""
        blk = self.new_node(title, "", x, y)
        for i, (nm, dt) in enumerate(tokens):
            blk["children"].append(self.new_node(nm, dt, x + 20, y + (i + 1) * (NH + 20)))
        return blk

    def visible(self, node):
        """深度优先展开顺序（跳过折叠子树）"""
        out = [node]
        if not node.get("collapsed"):
            for c in sorted(node.get("children", []), key=lambda n: (n["y"], id(n))):
                out += self.visible(c)
        return out

    def ordered(self):
        """执行/保存顺序 = 根按 Y 排序 + 每棵子树深度优先"""
        out = []
        for n in sorted(self.nodes, key=lambda n: (n["y"], id(n))):
            out += self.visible(n)
        return out

    def flatten_tokens(self):
        return [(n["name"], n["data"]) for n in self.ordered()]

    def subtree(self, node):
        out = [node]
        for c in node.get("children", []):
            out += self.subtree(c)
        return out

    # ---------- 界面 ----------
    def build_ui(self):
        self.root.configure(bg=PANEL)
        bar = tk.Frame(self.root, bg=PANEL); bar.pack(fill="x")
        tk.Label(bar, text="Simply", bg=PANEL, fg="#7aa2f7",
                 font=("Microsoft YaHei UI", 10, "bold")).pack(side="left", padx=(10, 6), pady=3)
        def btn(t, c, primary=False):
            b = tk.Button(bar, text=t, command=c, bg=("#2f6fdd" if primary else "#1f2335"),
                          fg="#fff", relief="flat", activebackground="#3f7fee", padx=9,
                          bd=0, highlightthickness=0)
            b.pack(side="left", padx=2, pady=3); return b
        btn("保存", self.save, primary=True)
        btn("运行", self.run)
        self.list_btn = btn("列表视图", self.toggle_view)
        self.mbtn = tk.Menubutton(bar, text="\u2630", bg="#1f2335", fg="#fff", relief="flat",
                                  activebackground="#3f7fee", padx=10, bd=0)
        mm = tk.Menu(self.mbtn, tearoff=0, bg=PANEL, fg=TEXT, activebackground=SEL)
        mm.add_command(label="加载", command=self.load)
        mm.add_separator()
        mm.add_command(label="载入猜数字示例", command=self.load_template)
        mm.add_command(label="自动布局", command=self.auto_layout)
        mm.add_command(label="撤销", command=self.undo)
        mm.add_separator()
        mm.add_command(label="放大", command=lambda: self.zoom_btn(1.25))
        mm.add_command(label="缩小", command=lambda: self.zoom_btn(0.8))
        mm.add_command(label="适应视图", command=self.fit)
        mm.add_separator()
        mm.add_command(label="服务器 data 查看器", command=self.toggle_side)
        mm.add_command(label="输出面板", command=self.toggle_out)
        self.mbtn.config(menu=mm)
        self.mbtn.pack(side="left", padx=2, pady=3)
        self.status = tk.Label(bar, text="", bg=PANEL, fg="#7fd6a0"); self.status.pack(side="right", padx=8)

        main = tk.Frame(self.root, bg=PANEL); main.pack(fill="both", expand=True)
        # 左侧查看器（默认隐藏）
        self.side = tk.Frame(main, bg="#131926", width=250)
        tk.Label(self.side, text="服务器 data（双击添加）", bg="#1a2233", fg="#b9c7e4",
                 font=("Microsoft YaHei UI", 9, "bold")).pack(fill="x")
        self.viewer = tk.Listbox(self.side, bg="#0f1420", fg=TEXT, selectbackground=SEL,
                                 selectforeground="#0b0b12", font=("Consolas", 9),
                                 activestyle="none", borderwidth=0, highlightthickness=0)
        self.viewer.pack(fill="both", expand=True, padx=4, pady=4)
        self.viewer.bind("<Double-Button-1>", self.viewer_add)
        tk.Button(self.side, text="刷新", command=self.refresh_viewer, bg="#26314d", fg="#fff",
                  relief="flat").pack(fill="x", padx=4, pady=(0, 4))
        self.vstatus = tk.Label(self.side, text="", bg="#131926", fg="#8fa3c8",
                                font=("Microsoft YaHei UI", 8)); self.vstatus.pack(fill="x", padx=4, pady=2)
        self.side_visible = False

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

        # 列表视图（v1 风格 token 列表，与图形共用同一份节点）
        self.listf = tk.Frame(self.root, bg=PANEL)
        lr = tk.Frame(self.listf, bg=PANEL); lr.pack(fill="x", padx=6, pady=4)
        tk.Label(lr, text="token:", bg=PANEL, fg=TEXT).pack(side="left")
        self.e_name = tk.Entry(lr, width=12); self.e_name.pack(side="left", padx=3)
        tk.Label(lr, text="data:", bg=PANEL, fg=TEXT).pack(side="left")
        self.e_data = tk.Entry(lr, width=34); self.e_data.pack(side="left", padx=3)
        for t, c in [("添加", self.list_add), ("更新", self.list_update), ("删除", self.list_delete),
                     ("上移", lambda: self.list_move(-1)), ("下移", lambda: self.list_move(1))]:
            tk.Button(lr, text=t, command=c, bg="#26314d", fg="#fff", relief="flat").pack(side="left", padx=2)
        self.list_sel_idx = None
        self.list_items_cache = []
        self.listc = tk.Canvas(self.listf, bg="#0f1420", highlightthickness=0)
        self.listc.pack(fill="both", expand=True, padx=6, pady=(0, 6))
        self.listc.bind("<Button-1>", self.list_click)
        self.listc.bind("<Double-Button-1>", lambda e: self.list_click(e))
        self.listc.bind("<MouseWheel>", self.list_wheel)

        # 输出面板（默认隐藏）
        self.out = scrolledtext.ScrolledText(self.root, height=7, bg="#0d0f16", fg="#9ece6a",
                                             insertbackground="#9ece6a", font=("Consolas", 10))
        self.out_visible = False

    # ---------- 布局打包（侧栏/输出按开关重排） ----------
    def _pack_main(self):
        for w in (self.side, self.listf, self.c, self.out):
            w.pack_forget()
        if self.side_visible:
            self.side.pack(side="left", fill="y")
        if self.view_mode == "list":
            self.listf.pack(fill="both", expand=True)
        else:
            self.c.pack(fill="both", expand=True)
        if self.out_visible:
            self.out.pack(fill="x")

    def toggle_side(self):
        self.side_visible = not self.side_visible
        self._pack_main()

    def toggle_out(self):
        self.out_visible = not self.out_visible
        self._pack_main()

    def log(self, s):
        self.out.insert("end", s + "\n"); self.out.see("end")

    # ---------- 视图变换（平滑缩放/平移） ----------
    def W2S(self, x, y): return x * self.zoom + self.ox, y * self.zoom + self.oy
    def S2W(self, x, y): return (x - self.ox) / self.zoom, (y - self.oy) / self.zoom
    def zoom_at(self, f, sx, sy):
        wx, wy = self.S2W(sx, sy)
        self.zoom = max(0.2, min(3.0, self.zoom * f))
        self.ox, self.oy = sx - wx * self.zoom, sy - wy * self.zoom
        self.redraw()
    def zoom_btn(self, f):
        self.zoom_at(f, self.c.winfo_width() / 2, self.c.winfo_height() / 2)
    def on_wheel(self, e):
        f = 1.12 if e.delta > 0 else 1 / 1.12
        self._zt = self.zoom * f
        self._zc = (e.x, e.y)
        self._zoom_step()
    def _zoom_step(self):
        if abs(self._zt - self.zoom) < 0.001:
            return
        self.zoom_at(self._zt / self.zoom * 0.35 + 0.65, self._zc[0], self._zc[1])
        self.root.after(14, self._zoom_step)
    def fit(self):
        if not self.nodes:
            self.zoom, self.ox, self.oy = 1.0, 60, 40; self.redraw(); return
        xs = [n["x"] for n in self.ordered()]; ys = [n["y"] for n in self.ordered()]
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
        for n in reversed(self.ordered()):
            if abs(wx - n["x"]) <= NW / 2 and abs(wy - n["y"]) <= NH / 2:
                return n
        return None
    def hit_collapse(self, wx, wy):
        for n in reversed(self.ordered()):
            if n.get("children"):
                bx, by = self.W2S(n["x"] + NW / 2 - 14, n["y"] + NH / 2 - 12)
                if abs(wx - (n["x"] + NW / 2 - 14)) <= 9 and abs(wy - (n["y"] + NH / 2 - 12)) <= 9:
                    return n
        return None
    def on_lpress(self, e):
        self.close_inline()
        wx, wy = self.S2W(e.x, e.y)
        n = self.hit_collapse(wx, wy)
        if n:
            self.snapshot()
            n["collapsed"] = not n.get("collapsed", False)
            self.dirty = True
            self.redraw(); return
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
        if n:
            self.sel = n; self.redraw()
            if n["name"] == "net":
                self.net_dialog(n)
            else:
                self.inline_edit(n)
    def snapshot(self):
        self.undo_stack.append(copy.deepcopy(self.nodes))
        if len(self.undo_stack) > 60: self.undo_stack.pop(0)
    def undo(self):
        if self.undo_stack:
            self.nodes = self.undo_stack.pop()
            self.sel = None; self.dirty = True
            self.redraw(); self.status.config(text="已撤销")
    def add_node(self, name, data="", parent=None):
        self.snapshot()
        x, y = self.S2W(self.c.winfo_width() / 2, self.c.winfo_height() / 2)
        n = len(self.ordered())
        node = self.new_node(name, data, round(x) + (n % 5) * 30, round(y) + (n % 4) * 26)
        if parent is not None:
            parent.setdefault("children", []).append(node)
            parent["collapsed"] = False
        else:
            self.nodes.append(node)
        self.sel = node; self.dirty = True
        self.redraw()
    def del_node(self):
        if self.sel is None: return
        self.snapshot()
        def remove(parents, node):
            for p in parents:
                if node in p.get("children", []):
                    p["children"].remove(node); return True
            return False
        if self.sel in self.nodes:
            self.nodes.remove(self.sel)
        else:
            for p in self.ordered():
                if remove([p], self.sel): break
        self.sel = None; self.dirty = True
        self.redraw()
    def dup_node(self):
        if self.sel is None: return
        self.snapshot()
        c = copy.deepcopy(self.sel); c["y"] += NH + 20
        def parent_of(node):
            for p in self.ordered():
                if node in p.get("children", []): return p
            return None
        p = parent_of(self.sel)
        if p: p["children"].append(c)
        else: self.nodes.append(c)
        self.sel = c; self.dirty = True
        self.redraw()
    def add_child(self):
        if self.sel is None: return
        self.add_node("nop", "", parent=self.sel)
    def toggle_collapse(self):
        if self.sel and self.sel.get("children"):
            self.snapshot()
            self.sel["collapsed"] = not self.sel.get("collapsed", False)
            self.dirty = True
            self.redraw()

    # ---------- 内联编辑（typein：在节点上直接打字） ----------
    def close_inline(self):
        if self.inline:
            try:
                self.inline.destroy()
            except Exception:
                pass
            self.inline = None
    def inline_edit(self, node):
        self.close_inline()
        ex, ey = self.W2S(node["x"] - NW / 2 + 48, node["y"] - 8)
        ent = tk.Entry(self.root, bg="#0f1420", fg="#7ec3ff", insertbackground="#fff",
                       relief="flat", highlightthickness=1, highlightbackground=SEL,
                       font=("Consolas", 10))
        ent.place(x=ex - 4, y=ey - 4, width=int(NW * self.zoom * 0.78), height=22)
        ent.insert(0, node["name"])
        ent.focus_set(); ent.select_range(0, "end")
        state = {"stage": 0, "name": "", "data": ""}
        def commit():
            if state["stage"] == 0:
                state["name"] = ent.get().strip() or "nop"
                state["stage"] = 1
                ent.delete(0, "end")
                ent.insert(0, node["data"])
                ent.config(fg="#f0c674")
                ent.select_range(0, "end")
            else:
                state["data"] = ent.get()
                self.snapshot()
                node["name"] = state["name"]
                node["data"] = state["data"]
                self.dirty = True
                self.close_inline()
                self.redraw()
        ent.bind("<Return>", lambda e: commit())
        ent.bind("<Tab>", lambda e: (commit(), "break")[1])
        ent.bind("<Escape>", lambda e: self.close_inline())
        ent.bind("<FocusOut>", lambda e: self.close_inline())
        self.inline = ent

    # ---------- 右键菜单 ----------
    def show_menu(self, e):
        wx, wy = self.S2W(e.x, e.y)
        n = self.node_at(wx, wy)
        m = tk.Menu(self.root, tearoff=0, bg=PANEL, fg=TEXT, activebackground=SEL)
        if n:
            m.add_command(label="内联编辑…", command=lambda: self.inline_edit(n))
            if n.get("children"):
                m.add_command(label=("展开" if n.get("collapsed") else "折叠") + "子树", command=self.toggle_collapse)
            m.add_command(label="添加子节点", command=self.add_child)
            m.add_command(label="复制", command=self.dup_node)
            m.add_command(label="删除（含子树）", command=self.del_node)
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

    # 编辑节点（旧弹窗保留给非内联场景）
    def edit_node(self, node):
        if node["name"] == "net":
            self.net_dialog(node); return
        self.inline_edit(node)

    # ---------- 列表视图（节点样式：块=卡片，内含多个 token 行） ----------
    LRH, TITLE, ROW = 52, 40, 34
    def toggle_view(self):
        self.close_inline()
        self.view_mode = "list" if self.view_mode == "graph" else "graph"
        self.list_btn.config(text="图形视图" if self.view_mode == "list" else "列表视图")
        if self.view_mode == "list":
            self.list_refresh()
        else:
            self.redraw()
        self._pack_main()

    def list_refresh(self):
        self.listc.delete("all")
        w = self.listc.winfo_width() or 420
        self.list_hit = []
        y = 6
        for r in sorted(self.nodes, key=lambda x: (x["y"], id(x))):
            if r.get("children"):
                self._draw_block(r, y, w)
                y += self.TITLE + (0 if r.get("collapsed") else len(r["children"]) * self.ROW) + 10
            else:
                self._draw_token_row(r, None, y, w, 0)
                y += self.LRH + 4
        self.listc.configure(scrollregion=(0, 0, w, max(y, self.listc.winfo_height())))

    def _draw_block(self, blk, y, w):
        sel = (self.sel is blk)
        poly = self.rrect(8, y, w - 8, y + self.TITLE, 10)
        self.listc.create_polygon(poly, fill="#20263c", outline=(SEL if sel else "#3d4a73"), width=2)
        self.draw_icon("label", "#73daca", 30, y + self.TITLE / 2 - 2, cv=self.listc)
        self.listc.create_text(52, y + self.TITLE / 2 - 3, anchor="w", text=blk["name"], fill="#e8eaf0",
                               font=("Microsoft YaHei UI", 10, "bold"))
        self.listc.create_text(52, y + self.TITLE / 2 + 10, anchor="w",
                               text="%d tokens" % len(blk["children"]), fill=DIM,
                               font=("Microsoft YaHei UI", 8))
        mark = "%d -" % len(blk["children"]) if not blk.get("collapsed") else "%d +" % len(blk["children"])
        self.listc.create_text(w - 24, y + self.TITLE / 2, text=mark, fill="#7fd6a0",
                               font=("Microsoft YaHei UI", 9, "bold"))
        self.list_hit.append((y, y + self.TITLE, blk, blk))
        if blk.get("collapsed"): return
        for i, c in enumerate(sorted(blk["children"], key=lambda x: (x["y"], id(x)))):
            self._draw_token_row(c, blk, y + self.TITLE + i * self.ROW, w, 1)

    def _draw_token_row(self, node, block, y, w, indent):
        sel = (self.sel is node)
        poly = self.rrect(8, y, w - 8, y + self.ROW, 8)
        self.listc.create_polygon(poly, fill=NODE, outline=(SEL if sel else "#33405e"), width=2)
        icon, color = icon_of(node["name"])
        cx = 30 + indent * 18
        self.draw_icon(icon, color, cx, y + self.ROW / 2 - 2, cv=self.listc)
        dt = node["data"] if node["data"] else ("零data" if node["name"] == "net" else "")
        txt = node["name"] + ("  |  " + dt if dt else "")
        if len(txt) > 44: txt = txt[:43] + "..."
        self.listc.create_text(cx + 22, y + self.ROW / 2, anchor="w", text=txt, fill=TEXT,
                               font=("Microsoft YaHei UI", 9))
        self.list_hit.append((y, y + self.ROW, node, block))

    def list_click(self, e):
        for y0, y1, node, block in self.list_hit:
            if y0 <= e.y <= y1:
                self.sel, self.sel_block = node, block
                self.e_name.delete(0, "end"); self.e_name.insert(0, node["name"])
                self.e_data.delete(0, "end"); self.e_data.insert(0, node["data"])
                self.list_refresh()
                kind = "块" if node is block and node.get("children") else ("块内" if block else "根")
                self.status.config(text="选中: %s（%s）" % (node["name"], kind))
                return

    def list_wheel(self, e):
        self.listc.yview_scroll(-1 if e.delta > 0 else 1, "units")

    def list_add(self):
        self.snapshot()
        nm = self.e_name.get().strip() or "nop"
        dt = self.e_data.get()
        if self.sel_block is not None:
            node = self.new_node(nm, dt, self.sel_block["x"] + 20, 0)
            self.sel_block["children"].append(node)
            self.sel_block["collapsed"] = False
            self.sel = node
        else:
            y = max([n["y"] for n in self.ordered()] or [0]) + NH + 20
            node = self.new_node(nm, dt, 40, y)
            self.nodes.append(node)
            self.sel, self.sel_block = node, None
        self.dirty = True
        self.list_refresh(); self.redraw()

    def list_update(self):
        if self.sel is None: return
        self.snapshot()
        self.sel["name"] = self.e_name.get().strip() or "nop"
        self.sel["data"] = self.e_data.get()
        self.dirty = True
        self.list_refresh(); self.redraw()

    def list_delete(self):
        if self.sel is None: return
        self.snapshot()
        if self.sel_block is not None:
            self.sel_block["children"].remove(self.sel)
        else:
            self.nodes.remove(self.sel)
        self.sel = None; self.sel_block = None; self.dirty = True
        self.list_refresh(); self.redraw()

    def list_move(self, d):
        if self.sel is None: return
        if self.sel_block is not None:
            kids = self.sel_block["children"]
            i = kids.index(self.sel); j = i + d
            if not (0 <= j < len(kids)): return
            self.snapshot()
            kids[i]["y"], kids[j]["y"] = kids[j]["y"], kids[i]["y"]
        else:
            i = self.nodes.index(self.sel); j = i + d
            if not (0 <= j < len(self.nodes)): return
            self.snapshot()
            self.nodes[i]["y"], self.nodes[j]["y"] = self.nodes[j]["y"], self.nodes[i]["y"]
        self.dirty = True
        self.list_refresh(); self.redraw()

    # ---------- 服务器查看器（网络节点，默认开 零data=空key） ----------
    def viewer_groups(self):
        keys = [b""]
        if self.key: keys.append(self.key)
        for n in self.ordered():
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
                    self.nodes.append(self.new_node(nm, dt, round(x) + (i % 6) * 30, round(y) + (i // 6) * 30))
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

    # ---------- 布局（树形：子节点缩进） ----------
    def auto_layout(self):
        if not self.nodes: return
        self.snapshot()
        w = self.c.winfo_width() or 900
        y = 40
        def place(node, d):
            nonlocal y
            node["x"] = 40 + d * 30
            node["y"] = y
            y += NH + 40
            for c in node.get("children", []):
                place(c, d + 1)
        for n in self.nodes:
            place(n, 0)
        self.fit()
        self.status.config(text="已树形布局 %d 个节点" % len(self.ordered()))

    def load_template(self):
        self.snapshot()
        self.nodes = [self.wrap_block("猜数字", guess_template())]
        self.sel = None; self.dirty = True
        self.fit()
        self.status.config(text="已载入猜数字示例：1 个块 / 28 个 token")

    # ---------- 服务器存取 ----------
    def save(self):
        if not self.key:
            try: self.key = boot_dll.get_id()
            except Exception as e:
                self.status.config(text="保存失败: " + str(e)); return
        payload = encode(self.flatten_tokens())
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
            self.nodes = [self.wrap_block("猜数字", guess_template())]
            self.save()
            return
        if toks == guess_template():
            self.nodes = [self.wrap_block("猜数字", toks)]
            self.sel = None; self.dirty = False
            self.redraw()
            self.status.config(text="已加载：1 个块 / %d 个 token（猜数字）" % len(toks))
            return
        cur = self.flatten_tokens()
        if cur == toks:
            self.redraw()
            return
        saved = None
        try:
            saved = json.load(open(STATE, encoding="utf-8"))["nodes"]
        except Exception:
            saved = None
        def flat_seq(nodes):
            out = []
            for n in nodes:
                out.append((n["name"], n["data"]))
                out += flat_seq(n.get("children", []))
            return out
        if saved is not None and flat_seq(saved) == toks:
            self.nodes = saved
        else:
            self.nodes = []
            for i, (nm, dt) in enumerate(toks):
                self.nodes.append(self.new_node(nm, dt, 40 + (i % 5) * (NW + 40), 40 + (i // 5) * (NH + 40)))
        self.sel = None; self.dirty = False
        self.redraw()
        self.status.config(text="已加载，共 %d 个节点" % len(self.ordered()))

    def after_loop(self):
        if not self.dirty:
            self.load(); self.refresh_viewer()
        self.root.after(3000, self.after_loop)

    def run(self):
        if not self.out_visible:
            self.out_visible = True
            self._pack_main()
        self.out.delete("1.0", "end")
        toks = self.flatten_tokens()
        self.log("--- 运行 %d 个节点（树形深度优先）---" % len(toks))
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

    def draw_icon(self, icon, color, cx, cy, cv=None):
        cv = cv or self.c
        for d in ICONS[icon]:
            for pts, closed in parse_path(d):
                p = [(cx + (px - 12) * 0.85, cy + (py - 12) * 0.85) for px, py in pts]
                cv.create_line(p, fill=color, width=2, capstyle="round", joinstyle="round")

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
        for n in self.ordered():
            self.draw_node(n)
        if self.dirty:
            self.status.config(text="%d 节点 | 缩放 %.2fx | 未保存" % (len(self.ordered()), self.zoom))
        else:
            self.status.config(text="%d 节点 | 缩放 %.2fx" % (len(self.ordered()), self.zoom))

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
        if n.get("children"):
            bx, by = self.W2S(n["x"] + NW / 2 - 16, n["y"] + NH / 2 - 14)
            self.c.create_oval(bx - 8, by - 8, bx + 8, by + 8, fill="#26314d", outline=SEL)
            self.c.create_text(bx, by, text=("+" if n.get("collapsed") else "-"), fill=TEXT,
                               font=("Microsoft YaHei UI", 10, "bold"))
            if n.get("collapsed"):
                self.c.create_text(self.W2S(n["x"] + NW / 2 - 30, n["y"] - 20), anchor="e",
                                   text="%d 子节点" % len(self.subtree(n)), fill=DIM, font=("Microsoft YaHei UI", 8))

if __name__ == "__main__":
    root = tk.Tk()
    App(root)
    root.mainloop()
