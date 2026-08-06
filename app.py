# app.py —— Simply Token 节点图编辑器（最小实现：NodeGraphQt + QCompleter，逻辑不变）
import copy, json, os, random, struct
from PySide6.QtWidgets import (QApplication, QMainWindow, QDockWidget, QListWidget, QToolBar,
    QMenu, QLabel, QTextEdit, QLineEdit, QDialog, QVBoxLayout, QFormLayout, QPushButton,
    QDialogButtonBox, QInputDialog, QListWidgetItem, QCompleter)
from PySide6.QtCore import Qt, QTimer, QStringListModel, QRectF, QPointF
from PySide6.QtGui import QAction, QColor, QFont, QPen, QBrush, QPixmap, QPainter, QIcon
from PySide6.QtSvg import QSvgRenderer
from NodeGraphQt.qgraphics.node_svg import SVGNodeItem
from NodeGraphQt import NodeGraph, BaseNodeSVG, NodeBaseWidget
from NodeGraphQt.constants import ViewerEnum, PipeLayoutEnum
import boot_dll

STATE = "app_state.json"

# ---------- 服务器协议 ----------
def encode(ts):
    o = b""
    for n, d in ts:
        nb, db = n.encode(), d.encode()
        o += struct.pack("<I", len(nb)) + nb + struct.pack("<I", len(db)) + db
    return o + b"\x00\x00\x00\x00"

def decode(blk):
    ts, i = [], 0
    while i + 4 <= len(blk):
        n = struct.unpack("<I", blk[i:i+4])[0]; i += 4
        if not n: break
        name = blk[i:i+n].decode("utf-8", "replace"); i += n
        if i + 4 > len(blk): break
        d = struct.unpack("<I", blk[i:i+4])[0]; i += 4
        ts.append((name, blk[i:i+d].decode("utf-8", "replace"))); i += d
    return ts

GUESS = [("int","target"),("int","guess"),("int","tries"),("rand","100"),("set","target"),
         ("print","已生成 1-100 的随机数，开始猜吧！"),("main",""),("inc","tries"),("input",""),
         ("set","guess"),("read","guess"),("read","target"),("eq",""),("ifz","notwin"),
         ("print","猜中了！用了 "),("read","tries"),("print",""),("end",""),("notwin",""),
         ("read","guess"),("read","target"),("gt",""),("ifz","lower"),("print","大了"),
         ("jmp","main"),("lower",""),("print","小了"),("jmp","main")]

# ---------- 数据模型 ----------
def node(n, d="", x=0.0, y=0.0, kids=None):
    return {"name": n, "data": d, "x": x, "y": y, "children": kids or [], "collapsed": False}

def wrap(title, ts):
    b = node(title, "", 40, 40)
    b["children"] = [node(n, d, 60, 100 + i * 60) for i, (n, d) in enumerate(ts)]
    return b

def ordered(ns):
    out = []
    def vis(n):
        out.append(n)
        for c in sorted(n.get("children", []), key=lambda x: (x["y"], id(x))): vis(c)
    for n in sorted(ns, key=lambda x: (x["y"], id(x))): vis(n)
    return out

def flatten(ns): return [(n["name"], n["data"]) for n in ordered(ns)]

# ---------- 输入补全（Singularity str_prefix_ci_us + QCompleter 轮子） ----------
def prefix(name, q):
    if not q: return False
    i = j = 0
    while i < len(name) and j < len(q):
        if name[i] == "_": i += 1; continue
        if q[j] == "_": j += 1; continue
        if name[i].lower() != q[j].lower(): return False
        i += 1; j += 1
    return j == len(q)

BASE = ["int","set","read","inc","add","sub","mul","div","rand","eq","gt","lt",
        "ifz","jmp","ret","end","nop","print","input","main","notwin","loop","exit","net","块"]

ICON_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "icons")
ICON_MAP = {"read":"var_read_payload", "set":"var_set_payload", "int":"const_payload",
            "inc":"add", "add":"add", "sub":"sub", "mul":"mul", "div":"div",
            "rand":"f32_const", "eq":"cond_payload", "gt":"cond_payload", "lt":"cond_payload",
            "ifz":"cond_payload", "jmp":"jump_payload", "nop":"key_pressed",
            "print":"exec", "input":"key_down", "net":"globe", "end":"end", "ret":"jump_payload"}
def icon_for(name, is_block=False):
    f = ICON_MAP.get(name, "block" if is_block else "label") + ".svg"
    return os.path.join(ICON_DIR, f)

# ---------- 类别配色（Singularity 巅峰版 palette） ----------
CAT = {
    "read": (200,224,160), "set": (232,200,120), "int": (127,184,216),
    "add": (94,200,232), "sub": (94,200,232), "mul": (94,200,232), "div": (94,200,232),
    "inc": (94,200,232), "nop": (94,200,232), "jmp": (94,200,232), "print": (94,200,232),
    "eq": (208,128,224), "gt": (208,128,224), "lt": (208,128,224), "ifz": (208,128,224),
    "input": (224,160,80), "net": (247,118,142), "end": (255,158,100),
}
def cat_color(name):
    return CAT.get(name, (115,218,202))

def completions(nodes):
    prios = {}
    def walk(ns, pp):
        for i, n in enumerate(ns):
            d = n["data"]
            cp = pp * (i + 1) * max(1, len(d.encode()) if d else 0)   # 父data优先级×位置×大小
            if not d and n["name"]: prios[n["name"]] = max(prios.get(n["name"], 0), cp)
            if n["children"]: walk(n["children"], cp)
    walk(nodes, 1.0)
    return sorted(prios, key=lambda k: -prios[k]) or list(BASE)

class CompleteEdit(QLineEdit):
    def __init__(self, text="", source=None):
        super().__init__(text)
        self._src = source or (lambda: BASE)
        self._m = QStringListModel(self)
        self._c = QCompleter(self._m, self)
        self._c.setCompletionMode(QCompleter.PopupCompletion)
        self.setCompleter(self._c)
        self.textChanged.connect(self._r)
    def _r(self, q):
        if not q: self._c.popup().hide(); return
        self._m.setStringList([n for n in self._src() if prefix(n, q)][:64])
        self._c.complete()
    def keyPressEvent(self, e):
        if e.key() == Qt.Key_Space and self._c.popup().isVisible():
            t = self._c.currentCompletion()
            if t: self.setText(t); self.setCursorPosition(len(t)); return
        super().keyPressEvent(e)

# ---------- VM（树形层级 + 返回标记，数据驱动 OPS） ----------
class VM:
    def __init__(self, out=print): self.out = out; self.reset()
    def reset(self): self.vars, self.stack, self.steps, self.depth = {}, [], 0, 0; self._inject = None
    def pop(self): return self.stack.pop() if self.stack else 0
    OPS = {
        "int":   lambda v, d: v.vars.setdefault(d, 0),
        "set":   lambda v, d: v.vars.__setitem__(d, v.pop()),
        "read":  lambda v, d: v.stack.append(v.vars.get(d, 0)),
        "inc":   lambda v, d: v.vars.__setitem__(d, v.vars.get(d, 0) + 1),
        "add":   lambda v, d: v.stack.append(v.pop() + v.pop()),
        "sub":   lambda v, d: v.stack.append((lambda a, b: b - a)(v.pop(), v.pop())),
        "mul":   lambda v, d: v.stack.append(v.pop() * v.pop()),
        "div":   lambda v, d: v.stack.append((lambda a, b: b // a if a else 0)(v.pop(), v.pop())),
        "rand":  lambda v, d: v.stack.append(random.randint(1, int(d or 100))),
        "eq":    lambda v, d: v.stack.append(1 if v.pop() == v.pop() else 0),
        "gt":    lambda v, d: v.stack.append((lambda a, b: 1 if b > a else 0)(v.pop(), v.pop())),
        "lt":    lambda v, d: v.stack.append((lambda a, b: 1 if b < a else 0)(v.pop(), v.pop())),
        "print": lambda v, d: v.out(d if d else str(v.pop())),
        "input": lambda v, d: v.stack.append(next(v._inject) if v._inject else v._ask()),
        "nop":   lambda v, d: None,
    }

    def run(self, nodes, max_steps=1000, trace=True):
        self.reset()
        st = [[list(nodes), 0]]                                  # 调用栈：父帧即返回标记
        while st and self.steps < max_steps:
            self.steps += 1
            f = st[-1]; lst, i = f
            if i >= len(lst):                                   # 层级结束：弹返回标记回上层
                st.pop()
                if trace and st: self.out("← 块结束，返回上层（弹返回标记，深度 %d）" % len(st))
                continue
            n = lst[i]; f[1] = i + 1
            if n["children"]:                                   # 层级推进：压返回标记
                st.append([list(n["children"]), 0]); self.depth = max(self.depth, len(st))
                if trace: self.out("→ 进入 %s（压返回标记，深度 %d）" % (n["name"] or "块", len(st)))
                continue
            act = self.exec(n["name"], n["data"], st)
            if act == "end": st.clear()
            elif act == "ret":
                if trace: self.out("← ret 返回（弹返回标记，深度 %d）" % max(1, len(st) - 1))
                st.pop()
        if self.steps >= max_steps: self.out("(达到步数上限，已停止)")
    def exec(self, name, data, st):
        fn = self.OPS.get(name)
        if fn: return fn(self, data)
        if name == "ifz":
            if self.pop() == 0: self._jump(data, st)
        elif name == "jmp": self._jump(data, st)
        elif name == "ret": return "ret" if len(st) > 1 else "end"
        elif name == "end": return "end"
        return None
    def _jump(self, t, st):
        i = self._find(t, st[-1][0])
        if i >= 0: st[-1][1] = i
        else: self.out("(跳转目标不存在: " + t + ")")
    def _find(self, t, ns):
        for i, n in enumerate(ns):
            if n["name"] == t: return i
        return -1
    def _ask(self):
        v, ok = QInputDialog.getInt(None, "输入", "请输入数字")
        return v if ok else 0

# ---------- NodeGraphQt 节点（Singularity 巅峰画法） ----------
ROW_H, TITLE_H, CARD_W, SWATCH_W = 24.0, 34.0, 340.0, 5.0
C_BG, C_EDGE, C_SEL, C_TITLE, C_DIM, C_TEXT, C_GUT = (32,38,60), (52,65,77), (61,74,115), (157,167,179), (102,113,125), (232,236,239), (74,85,96)

def icon_pixmap(name, size, color=None):
    try:
        p = QPixmap(size, size); p.fill(Qt.transparent)
        pr = QPainter(p)
        QSvgRenderer(icon_for(name)).render(pr)
        pr.end()
        return p
    except Exception:
        return None

class BlockCardItem(SVGNodeItem):
    """块卡片：标题栏 + 内部 token 行 + 折叠（严格对齐 Singularity views 画法）"""
    def __init__(self, name="block", parent=None):
        super().__init__(name, parent)
        self._n = None; self._app = None; self._row = -1
    def _draw_node_horizontal(self):
        super()._draw_node_horizontal()
        if self._n and self._n.get("children"):
            rows = 0 if self._n.get("collapsed") else len(self._n["children"])
            self._width, self._height = CARD_W, TITLE_H + rows * ROW_H + 8.0
            self.update()
    def paint(self, painter, option, widget):
        n = self._n
        if not n or not n.get("children"):
            super().paint(painter, option, widget); return
        painter.save()
        w, h = self._width, self._height
        r = QRectF(0, 0, w, h)
        painter.setPen(QPen(QColor(*C_SEL) if self.selected else QColor(*C_EDGE), 2))
        painter.setBrush(QColor(*C_BG)); painter.drawRoundedRect(r, 10, 10)
        # 缩进槽
        painter.setPen(Qt.NoPen); painter.setBrush(QColor(*C_GUT))
        painter.drawRect(QRectF(12, 14, 2, 20))
        # 标题
        painter.setPen(QColor(*C_TITLE))
        painter.setFont(QFont("Microsoft YaHei UI", 10, QFont.Bold))
        painter.drawText(QRectF(22, 6, w - 84, 22), Qt.AlignLeft | Qt.AlignVCenter, n.get("name") or "块")
        # 折叠按钮
        bx, by = w - 34, 9
        painter.setPen(QPen(QColor(*C_TITLE), 1)); painter.setBrush(QColor("#26314d"))
        painter.drawEllipse(QRectF(bx, by, 16, 16))
        painter.setPen(QColor(*C_TEXT)); painter.setFont(QFont("Microsoft YaHei UI", 9, QFont.Bold))
        painter.drawText(QRectF(bx, by - 1, 16, 16), Qt.AlignCenter, "+" if n.get("collapsed") else "-")
        if n.get("collapsed"):
            painter.setPen(QColor(*C_DIM)); painter.setFont(QFont("Microsoft YaHei UI", 8))
            painter.drawText(QRectF(22, h - 26, w - 44, 20), Qt.AlignLeft, "%d tokens" % len(n["children"]))
            painter.restore(); return
        # token 行
        kids = sorted(n["children"], key=lambda c: (c["y"], id(c)))
        fname = QFont("Microsoft YaHei UI", 11); fsum = QFont("Microsoft YaHei UI", 9)
        for i, c in enumerate(kids):
            y0 = TITLE_H + i * ROW_H
            col = QColor(*cat_color(c["name"]))
            if self._row == i:
                painter.setPen(Qt.NoPen); painter.setBrush(QColor(*C_EDGE))
                painter.drawRect(QRectF(2, y0, w - 4, ROW_H))
            # 状态条
            painter.setPen(Qt.NoPen); painter.setBrush(col)
            painter.drawRect(QRectF(8, y0 + 5, SWATCH_W, 14))
            # 图标
            ic = icon_pixmap(c["name"], 16)
            if ic: painter.drawPixmap(int(18), int(y0 + 4), ic)
            # 名称（类别色）
            painter.setPen(col); painter.setFont(fname)
            painter.drawText(QRectF(40, y0, 170, ROW_H), Qt.AlignLeft | Qt.AlignVCenter, c["name"])
            # 摘要（亮色）
            if c["data"]:
                painter.setPen(QColor(*C_TEXT)); painter.setFont(fsum)
                painter.drawText(QRectF(216, y0, w - 224, ROW_H), Qt.AlignLeft | Qt.AlignVCenter, "  |  " + c["data"])
            # 分隔线
            painter.setPen(QPen(QColor(32, 38, 60), 1))
            painter.drawLine(QPointF(4, y0 + ROW_H), QPointF(w - 4, y0 + ROW_H))
        painter.restore()
    def mousePressEvent(self, e):
        n = self._n
        if n and n.get("children"):
            p = e.pos()
            if QRectF(self._width - 34, 9, 16, 16).contains(p):
                if self._app: self._app.toggle_fold(self)
                self.update(); e.accept(); return
        super().mousePressEvent(e)
    def mouseDoubleClickEvent(self, e):
        n = self._n
        if n and n.get("children") and not n.get("collapsed"):
            r = int((e.pos().y() - TITLE_H) // ROW_H)
            kids = sorted(n["children"], key=lambda c: (c["y"], id(c)))
            if 0 <= r < len(kids):
                if self._app: self._app.edit(kids[r])
                e.accept(); return
        super().mouseDoubleClickEvent(e)

class TokNode(BaseNodeSVG):
    __identifier__ = "simply"; NODE_NAME = "token"
    def __init__(self):
        super().__init__(BlockCardItem)
        self._n = None; self._app = None
        self.add_input("in"); self.add_output("out")
        self.add_text_input("data", "data", tab="内容")
    def show_kids(self):
        if self._n: self.view._n = self._n
        self.view.setToolTip(self.tooltip_text())
    def tooltip_text(self):
        n = self._n or {}
        p = ["<b>%s</b>" % (n.get("name") or "块")]
        if n.get("data"): p.append("data: " + n["data"])
        if n.get("children"): p.append("子树: %d 个 token" % len(n["children"]))
        try:
            ins = [x.node().name for x in self.input(0).connected_ports()]
            outs = [x.node().name for x in self.output(0).connected_ports()]
            if ins: p.append("输入连线 \u2190 " + ", ".join(ins))
            if outs: p.append("输出连线 \u2192 " + ", ".join(outs))
        except Exception: pass
        return "<br/>".join(p)

# ---------- 主窗口 ----------
class App(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Simply Token 节点图编辑器"); self.resize(1280, 800)
        self.nodes, self.key, self.dirty, self.undo_stack = [], b"", False, []
        self.vm = VM()
        self.g = NodeGraph(); self.g.register_node(TokNode)
        self.g.set_background_color(15, 18, 24)   # #0f1218 Singularity 深色
        self.g.set_grid_mode(ViewerEnum.GRID_DISPLAY_DOTS.value)   # 巅峰：点阵底
        self.g.set_grid_color(31, 37, 51)
        self.g.set_pipe_style(PipeLayoutEnum.CURVED.value)
        self.g.set_pipe_collision(True); self.g.set_pipe_slicing(True)
        self.view = self.g.widget; self._items = {}
        self.setCentralWidget(self.view)   # 关键：把图挂到窗口中央
        self.g.node_double_clicked.connect(self.dbl)
        self.g.nodes_deleted.connect(self.deled)
        self.g.node_selection_changed.connect(self.sel_changed)
        self._ui()
        self.load(); self.refresh()
        QTimer.singleShot(800, self.g.fit_to_selection)   # 等窗口就绪再框选
        QTimer.singleShot(3000, self.loop)
# 场景
    def refresh(self):
        for n in list(self.g.all_nodes()): self.g.delete_node(n)
        self._items = {}
        for n in self.nodes:
            t = self.g.create_node("simply.TokNode", name=n["name"])
            t._n = n; t._app = self; t.set_property("data", n["data"]); t.set_pos(n["x"], n["y"])
            t.view._n = n; t.view._app = self
            if n["children"]:                                  # 块=深色巅峰卡片
                t.set_svg(icon_for("block", True))
                t.set_color(*C_BG); t.view.border_color = (*C_EDGE, 255)
                t.view.text_color = (*C_TITLE, 255)
            else:                                              # token=类别色图标
                t.set_svg(icon_for(n["name"], False))
                t.set_color(*cat_color(n["name"]))
                t.view.border_color = (*cat_color(n["name"]), 255)
                t.view.text_color = (*C_TEXT, 255)
            t.show_kids(); self._items[id(n)] = t
            t.hide_widget("data", push_undo=False)             # 巅峰：data 走双击编辑，不占卡片
            if n["children"]: t.view._draw_node_horizontal()   # 应用块卡片尺寸
            t.view.setToolTip(t.tooltip_text())
        r = sorted(self.nodes, key=lambda x: (x["y"], id(x)))
        for i in range(len(r) - 1):
            self._items[id(r[i])].output(0).connect_to(self._items[id(r[i + 1])].input(0))
        for it in self.g.scene().items():                       # 连线=Singularity 绿 #62c982
            if it.__class__.__name__ == "PipeItem" and getattr(it, "_output_port", None):
                it.set_pipe_styling((98, 201, 130, 220), 2, 0)
        self.status.setText("%d 根 / %d token%s" % (len(self.nodes), len(ordered(self.nodes)),
                             " 未保存" if self.dirty else ""))
    def sync(self):
        for n in self.nodes:
            t = self._items.get(id(n))
            if not t: continue
            try: n["x"], n["y"] = t.pos()
            except Exception: pass
            try: n["data"] = t.get_property("data") or n["data"]
            except Exception: pass
    def dbl(self, node):
        n = getattr(node, "_n", None)
        if n:
            self.conn_detail(node)          # 双击连线细节
            self.highlight_pipes(node)
            if n["name"] == "net" and n["data"]:
                self.load_key(n["data"], n)
            else:
                self.edit(n)
    def conn_detail(self, t):
        n = getattr(t, "_n", None)
        if not n: return
        self.out_dock.setVisible(True)
        self.out.append("\u2500\u2500 %s%s \u2500\u2500" % (n["name"], (" | " + n["data"]) if n["data"] else ""))
        if n["children"]: self.out.append("   子树 %d 个 token" % len(n["children"]))
        try:
            ins = [x.node().name for x in t.input(0).connected_ports()]
            outs = [x.node().name for x in t.output(0).connected_ports()]
            if ins: self.out.append("   输入连线 \u2190 " + ", ".join(ins))
            if outs: self.out.append("   输出连线 \u2192 " + ", ".join(outs))
            if not ins and not outs: self.out.append("   （无连线）")
        except Exception: pass
        c = cat_color(n["name"])
        self.status.setText("%s%s | RGB(%d,%d,%d)%s" % (n["name"], (" | "+n["data"]) if n["data"] else "",
                             *c, (" | 子树 %d" % len(n["children"])) if n["children"] else ""))
    def highlight_pipes(self, t, ms=1800):
        try:
            for p in (t.input(0), t.output(0)):
                for pipe in p.view.connected_pipes(): pipe.set_pipe_styling((160, 240, 255, 255), 3, 0)
            QTimer.singleShot(ms, lambda: self.reset_pipes(t))
        except Exception: pass
    def reset_pipes(self, t):
        try:
            for p in (t.input(0), t.output(0)):
                for pipe in p.view.connected_pipes(): pipe.reset()
        except Exception: pass
    def deled(self, nodes):
        rm = {id(getattr(x, "_n", None)) for x in nodes if getattr(x, "_n", None)}
        if not rm: return
        self.snap()
        self.nodes = [n for n in self.nodes if id(n) not in rm]
        for n in self.nodes: n["children"] = [c for c in n["children"] if id(c) not in rm]
        self.dirty = True; self.refresh()
    def toggle_fold(self, t):
        n = getattr(t, "_n", None)
        if not n or not n.get("children"): return
        n["collapsed"] = not n.get("collapsed", False)
        if hasattr(t, "_draw_node_horizontal"): t._draw_node_horizontal()
        elif hasattr(t, "view"): t.view._draw_node_horizontal()
        self.status.setText("%s | %s (%d tokens)" % (n["name"],
                             "已折叠" if n["collapsed"] else "已展开", len(n["children"])))
    def sel_changed(self, selected, deselected):
        if not selected: return
        n = getattr(selected[0], "_n", None)
        if n:
            c = cat_color(n["name"])
            self.status.setText("%s%s | RGB(%d,%d,%d)%s" % (n["name"], (" | "+n["data"]) if n["data"] else "",
                                 *c, (" | 子树 %d" % len(n["children"])) if n["children"] else ""))
    # 编辑
    def ask(self, title, init="", ph=""):
        d = QDialog(self); d.setWindowTitle(title)
        lay = QVBoxLayout(d)
        e = CompleteEdit(init, lambda: completions(self.nodes)); e.setPlaceholderText(ph)
        lay.addWidget(e)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(d.accept); bb.rejected.connect(d.reject)
        lay.addWidget(bb); e.setFocus()
        return (e.text().strip(), True) if d.exec() == QDialog.Accepted else (None, False)
    def edit(self, n):
        if n["children"]:
            t, ok = self.ask("编辑块", n["name"])
            if ok and t: self.snap(); n["name"] = t or "块"; self.dirty = True; self.refresh()
            return
        d = QDialog(self); d.setWindowTitle("编辑 token")
        f = QFormLayout(d)
        e1 = CompleteEdit(n["name"], lambda: completions(self.nodes)); e2 = QLineEdit(n["data"])
        f.addRow("token", e1); f.addRow("data", e2)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(d.accept); bb.rejected.connect(d.reject); f.addRow(bb)
        if d.exec() == QDialog.Accepted:
            self.snap(); n["name"] = e1.text().strip() or "nop"; n["data"] = e2.text()
            self.dirty = True; self.refresh()
    def quick(self):
        t, ok = self.ask("快速添加 token（补全）", "", "输入前缀，空格/回车补全插入")
        if ok and t: self.add(t)
    def snap(self):
        self.undo_stack.append(copy.deepcopy(self.nodes))
        if len(self.undo_stack) > 60: self.undo_stack.pop(0)
    def undo(self):
        if self.undo_stack: self.nodes = self.undo_stack.pop(); self.dirty = True; self.refresh()
    def add(self, name, data="", parent=None):
        self.snap()
        n = node(name, data, 120 + len(self.nodes) * 30, 120 + len(self.nodes) * 30)
        parent["children"].append(n) if parent else self.nodes.append(n)
        self.dirty = True; self.refresh()
    # 服务器查看器
    def viewer_groups(self):
        keys = [b""] + ([self.key] if self.key else [])
        for n in self.nodes:
            d = n["data"].encode("utf-8")
            if d and d not in keys: keys.append(d)
        groups = []
        for k in keys:
            try: toks = decode(boot_dll.fetch(k)) if k else []
            except Exception: toks = []
            groups.append((k, toks))
        return groups
    def refresh_viewer(self):
        self.listw.clear()
        for k, toks in self.viewer_groups():
            label = "<空 key> 零data" if not k else k.decode("utf-8", "replace")[:20]
            self.listw.addItem("\u25b8 " + label + "（" + str(len(toks)) + "）")
            for nm, dt in toks:
                it = QListWidgetItem("   " + nm + ("  |  " + dt if dt else ""))
                it.setData(Qt.UserRole, (nm, dt)); self.listw.addItem(it)
        self.listw.addItem("---- %d 组 ----" % len(self.viewer_groups()))
    def add_viewer(self):
        it = self.listw.currentItem()
        p = it.data(Qt.UserRole) if it else None
        if p: self.add(*p)
    # 布局/示例
    def layout(self):
        if not self.nodes: return
        self.snap()
        self.g.auto_layout_nodes()          # 库内置树形/流程自动布局
        self.sync(); self.refresh()
    def demo(self):
        self.snap(); self.nodes = [wrap("猜数字", GUESS)]; self.dirty = True
        self.refresh()
    # 服务器存取
    def save(self):
        self.sync()
        if not self.key:
            try: self.key = boot_dll.get_id()
            except Exception as e: self.status.setText("保存失败: " + str(e)); return
        payload = encode(flatten(self.nodes))
        try:
            idx = boot_dll.upload(self.key, payload)
            for _ in range(50):
                try:
                    if boot_dll.fetch(self.key) == payload: break
                except Exception: break
                boot_dll.vote(self.key, idx)
            self.dirty = False
            json.dump({"nodes": self.nodes}, open(STATE, "w", encoding="utf-8"), ensure_ascii=False)
            self.status.setText("已保存 idx=%d（确认）" % idx if boot_dll.fetch(self.key) == payload else "已保存 idx=%d" % idx)
        except Exception as e:
            self.status.setText("保存失败: " + str(e))
    def load(self):
        try: self.key = boot_dll.get_id()
        except Exception as e: self.status.setText("无法获取 id: " + str(e)); return
        try: toks = decode(boot_dll.fetch(self.key))
        except Exception: toks = []
        if not toks:                                   # 服务器不可达 → 回退本地 state
            try: self.nodes = json.load(open(STATE, encoding="utf-8"))["nodes"]
            except Exception: pass
            self.dirty = False; return
        if toks == [("editor", ""), ("rerun", "")]:
            self.nodes = [wrap("猜数字", GUESS)]; self.save(); return
        if toks == GUESS:
            self.nodes = [wrap("猜数字", toks)]; self.dirty = False
            self.status.setText("已加载：1 块 / %d token" % len(toks)); return
        if flatten(self.nodes) == toks: return
        saved = None
        try: saved = json.load(open(STATE, encoding="utf-8"))["nodes"]
        except Exception: saved = None
        def flat_seq(ns):
            out = []
            for n in ns:
                out.append((n["name"], n["data"])); out += flat_seq(n["children"])
            return out
        if saved is not None and flat_seq(saved) == toks:
            self.nodes = saved
        else:
            self.nodes = [node(nm, dt, 40 + (i % 5) * 240, 40 + (i // 5) * 90)
                          for i, (nm, dt) in enumerate(toks)]
        self.dirty = False
    def load_key(self, key, net_node=None):
        try:
            toks = decode(boot_dll.fetch(key.encode())) if key else []
            if not toks: return
            self.snap()
            for i, (nm, dt) in enumerate(toks):
                self.nodes.append(node(nm, dt, 100 + (i % 6) * 30, 100 + (i // 6) * 30))
            if net_node: net_node["data"] = key
            self.dirty = True; self.refresh()
        except Exception: pass
    def loop(self):
        if not self.dirty: self.load(); self.refresh_viewer()
        QTimer.singleShot(3000, self.loop)
    # 运行
    def run(self):
        self.out_dock.setVisible(True); self.out.clear()
        toks = flatten(self.nodes)
        self.out.append("--- 运行 %d 个 token（树形层级 + 返回标记）---" % len(toks))
        self.vm.out = self.out.append
        self.vm.run(self.nodes)
        self.status.setText("运行结束，共 %d 步，最大层级 %d" % (self.vm.steps, self.vm.depth))
    def toggle_side(self): self.side.setVisible(not self.side.isVisible())
    def toggle_out(self): self.out_dock.setVisible(not self.out_dock.isVisible())

    def _ui(self):
        bar = QToolBar(); bar.setMovable(False); self.addToolBar(bar)
        for t, fn in [("保存", self.save), ("运行", self.run)]:
            a = QAction(t, self); a.triggered.connect(fn); bar.addAction(a)
        m = QMenu(self)
        am = m.addMenu("添加")
        for label, names in [("变量", ["int","set","read","inc"]), ("运算", ["add","sub","mul","div","rand","eq","gt","lt"]),
                             ("控制", ["ifz","jmp","ret","end","nop"]), ("交互", ["print","input"]),
                             ("标签", ["main","notwin","loop","exit"]), ("网络", ["net"])]:
            sub = am.addMenu(label)
            for nm in names: sub.addAction(nm, lambda k=nm: self.add(k))
        am.addAction("新建块", lambda: self.add("块"))

        for t, fn in [("加载", self.load), ("猜数字示例", self.demo), ("自动布局", self.layout),
                      ("撤销", self.undo), ("快速添加（补全）", self.quick),
                      ("服务器查看器", self.toggle_side), ("输出面板", self.toggle_out)]:
            m.addAction(t, fn)
        bar.addAction("☰", m.popup)
        self.status = QLabel(""); bar.addWidget(self.status)
        self.side = QDockWidget("服务器 data（双击添加）", self)
        self.side.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        self.listw = QListWidget()
        self.listw.setStyleSheet("QListWidget{background:#131926;color:#b9c7e4;border:none;font-family:Consolas;}"
                                  "QListWidget::item{padding:2px 4px;}"
                                  "QListWidget::item:selected{background:#26314d;}")
        self.listw.itemDoubleClicked.connect(lambda _: self.add_viewer())
        self.side.setWidget(self.listw)
        self.addDockWidget(Qt.LeftDockWidgetArea, self.side)
        self.side.setVisible(False)              # 巅峰：默认干净画布，菜单/快捷键再开
        self.out_dock = QDockWidget("输出", self)
        self.out = QTextEdit()
        self.out.setReadOnly(True)
        self.out.setMaximumHeight(160)
        self.out.setStyleSheet("background:#0d0f16;color:#9ece6a;font-family:Consolas;")
        self.out_dock.setWidget(self.out)
        self.addDockWidget(Qt.BottomDockWidgetArea, self.out_dock)
        self.out_dock.setVisible(False)

def main():
    import sys, ctypes
    app = QApplication(sys.argv)
    w = App(); w.show()
    try:
        hwnd = int(w.winId())
        ctypes.windll.user32.ShowWindow(hwnd, 5)
        ctypes.windll.user32.SetForegroundWindow(hwnd)
    except Exception: pass
    sys.exit(app.exec())

if __name__ == "__main__":
    main()