# app.py —— Simply Token 节点图编辑器（PySide6/Qt 轮子版）
# QGraphicsView(缩放/平移/拖动内置) + QSvgRenderer(SVG图标，复用 JUST/Singularity)
# 块节点=大卡片内含多个 token 行；服务器存取/投票/查看器逻辑不变
import copy, json, math, os, random, struct
from PySide6.QtWidgets import (QApplication, QMainWindow, QGraphicsView, QGraphicsScene,
    QGraphicsItem, QGraphicsPathItem, QGraphicsTextItem, QDockWidget, QListWidget,
    QToolBar, QMenu, QLabel, QTextEdit, QLineEdit, QDialog, QFormLayout, QHBoxLayout,
    QVBoxLayout, QWidget, QPushButton, QMessageBox, QDialogButtonBox, QInputDialog)
from PySide6.QtGui import QPen, QBrush, QColor, QFont, QPainterPath, QPainter, QPixmap, QAction, QTransform
from PySide6.QtCore import Qt, QRectF, QPointF, QTimer
from PySide6.QtSvg import QSvgRenderer
import boot_dll

# ---------- 块编解码 ----------
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

# ---------- SVG 图标（QSvgRenderer 渲染，零手写解析） ----------
ICON_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "icons")
ICON_MAP = {"read": "var_read_payload", "set": "var_set_payload", "int": "const_payload",
            "inc": "add", "add": "add", "sub": "sub", "mul": "mul", "div": "div",
            "rand": "f32_const", "eq": "cond_payload", "gt": "cond_payload", "lt": "cond_payload",
            "ifz": "cond_payload", "jmp": "jump_payload", "nop": "key_pressed",
            "print": "exec", "input": "key_down", "net": "globe", "end": "end"}
_icon_cache = {}
def icon_pix(name, size=22):
    key = (name, size)
    if key not in _icon_cache:
        f = os.path.join(ICON_DIR, ICON_MAP.get(name, "label") + ".svg")
        pm = QPixmap(size, size); pm.fill(Qt.transparent)
        p = QPainter(pm); QSvgRenderer(f).render(p); p.end()
        _icon_cache[key] = pm
    return _icon_cache[key]

# ---------- 数据模型 ----------
def new_node(name, data="", x=0.0, y=0.0):
    return {"name": name, "data": data, "x": x, "y": y, "children": [], "collapsed": False}

def wrap_block(title, tokens, x=40.0, y=40.0):
    blk = new_node(title, "", x, y)
    for i, (nm, dt) in enumerate(tokens):
        blk["children"].append(new_node(nm, dt, x + 20, y + (i + 1) * 60))
    return blk

def block_height(node):
    if not node.get("children"): return 64
    if node.get("collapsed"): return 40
    return 40 + len(node["children"]) * 34

def ordered(nodes):
    out = []
    def vis(n):
        out.append(n)                 # collapsed 只是视图状态，不影响保存/执行顺序
        for c in sorted(n.get("children", []), key=lambda x: (x["y"], id(x))):
            vis(c)
    for n in sorted(nodes, key=lambda x: (x["y"], id(x))):
        vis(n)
    return out

def flatten(nodes):
    return [(n["name"], n["data"]) for n in ordered(nodes)]

def subtree(n):
    out = [n]
    for c in n.get("children", []):
        out += subtree(c)
    return out


# ---------- 迷你 VM（与旧版一致，input 可注入） ----------
class VM:
    def __init__(self, out=print):
        self.out = out
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
                val, ok = QInputDialog.getInt(None, "输入", "请输入数字")
                val = val if ok else 0
            self.stack.append(val)
        elif name == "ifz":
            if self.pop() == 0: self.jump(data, tokens)
        elif name == "jmp":   self.jump(data, tokens)
        elif name == "end":   self.pc = len(tokens)
        elif name == "nop":   pass

# ---------- Qt 视图（缩放/平移/拖动全内置） ----------
class View(QGraphicsView):
    def __init__(self, app):
        super().__init__()
        self.app = app
        self.setRenderHint(QPainter.Antialiasing)
        self.setDragMode(QGraphicsView.ScrollHandDrag)   # 中/右键拖动平移（内置）
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setBackgroundBrush(QColor("#0f1218"))
        self.setMouseTracking(True)
    def wheelEvent(self, e):                              # 滚轮缩放（内置 anchor）
        f = 1.15 if e.angleDelta().y() > 0 else 1 / 1.15
        self.scale(f, f)
    def contextMenuEvent(self, e):
        item = self.itemAt(e.pos())
        self.app.context_menu(item, e.globalPos())


# ---------- 节点项（QGraphicsItem，绘制即一切） ----------
BW = 320
BG, CARD, ROWBG, EDGE = QColor("#1c2436"), QColor("#20263c"), QColor("#233052"), QColor("#4f8cff")
SELC, TEXTC, DIMC, GRIDC = QColor("#4f8cff"), QColor("#e8eaf0"), QColor("#8fa3c8"), QColor("#232c42")
F_B = QFont("Microsoft YaHei UI", 10, QFont.Bold)
F_N = QFont("Microsoft YaHei UI", 9)
F_S = QFont("Microsoft YaHei UI", 8)

def trun(s, n):
    return s if len(s) <= n else s[:n - 1] + "..."

class BlockItem(QGraphicsItem):
    def __init__(self, node):
        super().__init__()
        self.node = node
        self.setFlags(QGraphicsItem.ItemIsMovable | QGraphicsItem.ItemIsSelectable)
        self.setZValue(1)
        self.setPos(node["x"], node["y"])
        self.click = None          # (kind, row)  kind: "title"/"row"/"collapse"
    def boundingRect(self):
        bh = block_height(self.node)
        return QRectF(-BW / 2, -bh / 2, BW, bh)
    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemPositionChange:
            self.node["x"], self.node["y"] = value.x(), value.y()
            self.app.refresh_edges()
        return super().itemChange(change, value)
    def paint(self, p, opt, w=None):
        bh = block_height(self.node)
        r = QRectF(-BW / 2, -bh / 2, BW, bh)
        p.setPen(QPen(SELC if self.isSelected() else QColor("#3d4a73"), 2))
        p.setBrush(CARD)
        p.drawRoundedRect(r, 10, 10)
        # 标题栏
        tcx = -BW / 2 + 20
        p.drawPixmap(int(tcx - 11), int(-bh / 2 + 9), icon_pix("block", 22))
        p.setPen(TEXTC); p.setFont(F_B)
        p.drawText(QRectF(tcx + 16, -bh / 2 + 4, 200, 18), Qt.AlignLeft | Qt.AlignVCenter, trun(self.node["name"], 18))
        p.setPen(DIMC); p.setFont(F_S)
        p.drawText(QRectF(tcx + 16, -bh / 2 + 20, 120, 14), Qt.AlignLeft, "%d tokens" % len(self.node["children"]))
        # 折叠按钮
        bx, by = BW / 2 - 20, -bh / 2 + 20
        p.setPen(SELC); p.setBrush(QColor("#26314d"))
        p.drawEllipse(QRectF(bx - 8, by - 8, 16, 16))
        p.setPen(TEXTC); p.setFont(F_B)
        p.drawText(QRectF(bx - 8, by - 9, 16, 16), Qt.AlignCenter, "+" if self.node.get("collapsed") else "-")
        if self.node.get("collapsed"): return
        # 内部 token 行
        kids = sorted(self.node["children"], key=lambda c: (c["y"], id(c)))
        for i, c in enumerate(kids):
            y0 = -bh / 2 + 40 + i * 34
            row = QRectF(-BW / 2 + 4, y0, BW - 8, 34)
            if self.click and self.click[0] == "row" and self.click[1] == i:
                p.setPen(SELC); p.setBrush(ROWBG)
                p.drawRect(row)
            p.drawPixmap(int(-BW / 2 + 16), int(y0 + 6), icon_pix(c["name"], 22))
            p.setPen(TEXTC); p.setFont(F_N)
            txt = c["name"] + ("  |  " + c["data"] if c["data"] else "")
            p.drawText(QRectF(-BW / 2 + 44, y0, BW - 60, 34), Qt.AlignLeft | Qt.AlignVCenter, trun(txt, 30))
            p.setPen(QColor("#20263c"))
            p.drawLine(QPointF(-BW / 2 + 4, y0 + 34), QPointF(BW / 2 - 4, y0 + 34))
    def hit(self, pos):
        bh = block_height(self.node)
        if pos.x() < -BW / 2 or pos.x() > BW / 2 or pos.y() < -bh / 2 or pos.y() > bh / 2:
            return None
        if pos.y() < -bh / 2 + 40:
            bx, by = BW / 2 - 20, -bh / 2 + 20
            if (pos.x() - bx) ** 2 + (pos.y() - by) ** 2 <= 100:
                return ("collapse", None)
            return ("title", None)
        i = int((pos.y() + bh / 2 - 40) // 34)
        if 0 <= i < len(self.node.get("children", [])):
            return ("row", i)
        return None
    def mousePressEvent(self, e):
        self.click = self.hit(e.pos())
        super().mousePressEvent(e)
    def mouseReleaseEvent(self, e):
        super().mouseReleaseEvent(e)
        if self.click:
            self.app.item_clicked(self, self.click)
            self.click = None
            self.update()

class TokenItem(QGraphicsItem):
    def __init__(self, node):
        super().__init__()
        self.node = node
        self.setFlags(QGraphicsItem.ItemIsMovable | QGraphicsItem.ItemIsSelectable)
        self.setZValue(1)
        self.setPos(node["x"], node["y"])
    def boundingRect(self):
        return QRectF(-100, -32, 200, 64)
    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemPositionChange:
            self.node["x"], self.node["y"] = value.x(), value.y()
            self.app.refresh_edges()
        return super().itemChange(change, value)
    def paint(self, p, opt, w=None):
        r = QRectF(-100, -32, 200, 64)
        p.setPen(QPen(SELC if self.isSelected() else QColor("#33405e"), 2))
        p.setBrush(BG)
        p.drawRoundedRect(r, 10, 10)
        p.drawPixmap(int(-86), -11, icon_pix(self.node["name"], 22))
        p.setPen(TEXTC); p.setFont(F_B)
        p.drawText(QRectF(-64, -24, 150, 20), Qt.AlignLeft | Qt.AlignVCenter, trun(self.node["name"], 14))
        p.setPen(DIMC); p.setFont(F_S)
        p.drawText(QRectF(-64, -2, 150, 18), Qt.AlignLeft, trun(self.node["data"] or "(空)", 16))


# ---------- 主窗口 ----------
STATE = "app_state.json"
class App(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Simply Token 节点图编辑器")
        self.resize(1280, 800)
        self.nodes, self.key = [], b""
        self.dirty, self.undo_stack = False, []
        self.vm = VM()
        self.build_ui()
        self.load()
        self.refresh_graph()
        self.fit()
        self.refresh_viewer()
        QTimer.singleShot(3000, self.after_loop)

    # ---------- UI ----------
    def build_ui(self):
        bar = QToolBar(); bar.setMovable(False)
        self.addToolBar(bar)
        def act(t, fn):
            a = QAction(t, self); a.triggered.connect(fn); bar.addAction(a); return a
        act("保存", self.save); act("运行", self.run)
        m = QMenu(self)
        for t, fn in [("加载", self.load), ("载入猜数字示例", self.load_template),
                      ("自动布局", self.auto_layout), ("撤销", self.undo),
                      ("适应视图", self.fit), ("放大", lambda: self.view.scale(1.2, 1.2)),
                      ("缩小", lambda: self.view.scale(1 / 1.2, 1 / 1.2)),
                      ("服务器查看器", self.toggle_side), ("输出面板", self.toggle_out)]:
            m.addAction(t, fn)
        bar.addAction("\u2630", m.popup)
        self.status = QLabel(""); bar.addWidget(self.status)

        self.scene = QGraphicsScene(self)
        self.view = View(self)
        self.view.setScene(self.scene)
        self.setCentralWidget(self.view)

        self.side = QDockWidget("服务器 data（双击添加）", self)
        self.side.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        self.listw = QListWidget()
        self.listw.itemDoubleClicked.connect(lambda _: self.viewer_add())
        self.side.setWidget(self.listw)
        self.addDockWidget(Qt.LeftDockWidgetArea, self.side)
        self.side.setVisible(False)

        self.out_dock = QDockWidget("输出", self)
        self.out = QTextEdit(); self.out.setReadOnly(True)
        self.out.setMaximumHeight(160)
        self.out.setStyleSheet("background:#0d0f16;color:#9ece6a;font-family:Consolas;")
        self.out_dock.setWidget(self.out)
        self.addDockWidget(Qt.BottomDockWidgetArea, self.out_dock)
        self.out_dock.setVisible(False)

    def log(self, s):
        self.out.append(s)

    # ---------- 场景 ----------
    def refresh_graph(self):
        self.scene.clear()
        self.edge_items = []
        for n in self.nodes:
            item = BlockItem(n) if n.get("children") else TokenItem(n)
            item.app = self
            self.scene.addItem(item)
        self.refresh_edges()
        self.status.setText("%d 根 / %d token | %s" % (len(self.nodes), len(ordered(self.nodes)),
                             "未保存" if self.dirty else ""))

    def refresh_edges(self):
        for e in getattr(self, "edge_items", []):
            self.scene.removeItem(e)
        self.edge_items = []
        roots = sorted(self.nodes, key=lambda n: (n["y"], id(n)))
        for i in range(len(roots) - 1):
            a, b = roots[i], roots[i + 1]
            aw = BW if a.get("children") else 200
            bw = BW if b.get("children") else 200
            pa = QPointF(a["x"] + aw / 2, a["y"])
            pb = QPointF(b["x"] - bw / 2, b["y"])
            path = QPainterPath(pa); path.lineTo(pb)
            e = QGraphicsPathItem(path)
            e.setPen(QPen(EDGE, 2))
            self.scene.addItem(e); self.edge_items.append(e)

    def fit(self):
        if self.nodes:
            self.view.fitInView(self.scene.itemsBoundingRect().adjusted(-60, -60, 60, 60),
                                Qt.KeepAspectRatio)

    # ---------- 交互 ----------
    def item_clicked(self, item, click):
        kind, row = click
        if kind == "collapse":
            self.snapshot(); item.node["collapsed"] = not item.node.get("collapsed", False)
            self.dirty = True; self.refresh_graph(); return
        if kind == "row":
            self.edit_token(item.node["children"][row]); return
        self.edit_block(item.node)

    def context_menu(self, item, gpos):
        m = QMenu(self)
        if item is not None and isinstance(item, (BlockItem, TokenItem)):
            node = item.node
            if node.get("children"):
                m.addAction("折叠/展开", lambda: self.toggle_collapse(node))
            m.addAction("添加子节点", lambda: self.add_node("nop", "", parent=node))
            m.addAction("编辑", lambda: self.edit_item(node))
            m.addAction("复制", lambda: self.dup_node(node))
            m.addAction("删除", lambda: self.del_node(node))
        else:
            for label, names in [("变量", ["int", "set", "read", "inc"]),
                                 ("运算", ["add", "sub", "mul", "div", "rand", "eq", "gt", "lt"]),
                                 ("控制", ["ifz", "jmp", "end", "nop"]),
                                 ("交互", ["print", "input"]),
                                 ("标签", ["main", "notwin", "loop", "exit"])]:
                sub = m.addMenu(label)
                for nm in names:
                    sub.addAction(nm, lambda k=nm: self.add_node(k))
            m.addAction("新建块", self.add_block)
            m.addAction("自动布局", self.auto_layout)
            m.addAction("载入猜数字示例", self.load_template)
        m.exec(gpos)

    def edit_item(self, node):
        if node.get("children"):
            self.edit_block(node)
        else:
            self.edit_token(node)

    def edit_token(self, node):
        d = QDialog(self); d.setWindowTitle("编辑 token")
        f = QFormLayout(d)
        e1, e2 = QLineEdit(node["name"]), QLineEdit(node["data"])
        f.addRow("token", e1); f.addRow("data", e2)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(d.accept); bb.rejected.connect(d.reject)
        f.addRow(bb)
        if d.exec() == QDialog.Accepted:
            self.snapshot()
            node["name"] = e1.text().strip() or "nop"
            node["data"] = e2.text()
            self.dirty = True; self.refresh_graph()

    def edit_block(self, node):
        d = QDialog(self); d.setWindowTitle("编辑块")
        f = QFormLayout(d)
        e1 = QLineEdit(node["name"])
        f.addRow("块名", e1)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(d.accept); bb.rejected.connect(d.reject)
        f.addRow(bb)
        if d.exec() == QDialog.Accepted:
            self.snapshot()
            node["name"] = e1.text().strip() or "块"
            self.dirty = True; self.refresh_graph()

    def snapshot(self):
        self.undo_stack.append(copy.deepcopy(self.nodes))
        if len(self.undo_stack) > 60: self.undo_stack.pop(0)
    def undo(self):
        if self.undo_stack:
            self.nodes = self.undo_stack.pop()
            self.dirty = True; self.refresh_graph()

    def add_node(self, name, data="", parent=None):
        self.snapshot()
        c = self.view.mapToScene(self.view.viewport().rect().center())
        node = new_node(name, data, c.x(), c.y())
        if parent is not None:
            parent["children"].append(node); parent["collapsed"] = False
        else:
            self.nodes.append(node)
        self.dirty = True; self.refresh_graph()
    def add_block(self):
        self.add_node("块")
    def del_node(self, node):
        self.snapshot()
        if node in self.nodes: self.nodes.remove(node)
        else:
            for p in self.nodes:
                if node in p.get("children", []): p["children"].remove(node); break
        self.dirty = True; self.refresh_graph()
    def dup_node(self, node):
        self.snapshot()
        c = copy.deepcopy(node); c["y"] += 40
        if node in self.nodes: self.nodes.append(c)
        else:
            for p in self.nodes:
                if node in p.get("children", []):
                    p["children"].append(c); break
        self.dirty = True; self.refresh_graph()
    def toggle_collapse(self, node):
        self.snapshot()
        node["collapsed"] = not node.get("collapsed", False)
        self.dirty = True; self.refresh_graph()


    # ---------- 服务器查看器 ----------
    def viewer_groups(self):
        keys = [b""]
        if self.key: keys.append(self.key)
        for n in ordered(self.nodes):
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
        self.listw.clear()
        for k, toks in self.viewer_groups():
            label = "<空 key> 零data" if not k else k.decode("utf-8", "replace")[:20]
            self.listw.addItem("\u25b8 " + label + "（" + str(len(toks)) + "）")
            for nm, dt in toks:
                self.listw.addItem("   " + nm + ("  |  " + dt if dt else ""))
        self.listw.addItem("---- %d 组 ----" % len(self.viewer_groups()))

    def viewer_add(self):
        it = self.listw.currentItem()
        if it and " | " in it.text():
            tok, dat = it.text().strip().split(" | ", 1)
            self.add_node(tok, dat)

    # ---------- 布局 ----------
    def auto_layout(self):
        if not self.nodes: return
        self.snapshot()
        w = self.view.viewport().width() or 900
        cols = max(1, int((w - 80) / (BW + 60)))
        y = 40.0
        for i, n in enumerate(sorted(self.nodes, key=lambda x: (x["y"], id(x)))):
            n["x"] = 40.0 + (i % cols) * (BW + 60)
            n["y"] = y
            y += block_height(n) + 50
        self.refresh_graph(); self.fit()

    def load_template(self):
        self.snapshot()
        self.nodes = [wrap_block("猜数字", guess_template())]
        self.dirty = True
        self.refresh_graph(); self.fit()
        self.status.setText("已载入猜数字示例：1 块 / %d token" % len(guess_template()))

    # ---------- 服务器存取 ----------
    def save(self):
        if not self.key:
            try: self.key = boot_dll.get_id()
            except Exception as e:
                self.status.setText("保存失败: " + str(e)); return
        payload = encode(flatten(self.nodes))
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
            self.status.setText("已保存 idx=%d（确认）" % idx if ok else "已保存 idx=%d" % idx)
        except Exception as e:
            self.status.setText("保存失败: " + str(e))

    def save_layout(self):
        try:
            json.dump({"nodes": self.nodes}, open(STATE, "w", encoding="utf-8"), ensure_ascii=False)
        except Exception:
            pass

    def load(self):
        try:
            self.key = boot_dll.get_id()
        except Exception as e:
            self.status.setText("无法获取 id: " + str(e)); return
        try:
            toks = decode(boot_dll.fetch(self.key))
        except Exception:
            toks = []
        if toks == [("editor", ""), ("rerun", "")]:
            self.nodes = [wrap_block("猜数字", guess_template())]
            self.save(); return
        if toks == guess_template():
            self.nodes = [wrap_block("猜数字", toks)]
            self.dirty = False
            self.status.setText("已加载：1 块 / %d token" % len(toks))
            return
        cur = flatten(self.nodes)
        if cur == toks: return
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
                self.nodes.append(new_node(nm, dt, 40 + (i % 5) * 240, 40 + (i // 5) * 90))
        self.dirty = False

    def after_loop(self):
        if not self.dirty:
            self.load(); self.refresh_viewer()
        QTimer.singleShot(3000, self.after_loop)

    # ---------- 运行/开关 ----------
    def run(self):
        if not self.out_dock.isVisible():
            self.out_dock.setVisible(True)
        self.out.clear()
        toks = flatten(self.nodes)
        self.out.append("--- 运行 %d 个 token（深度优先）---" % len(toks))
        self.vm.out = self.out.append
        self.vm.run(toks)
        self.status.setText("运行结束，共 %d 步" % self.vm.steps)

    def toggle_side(self):
        self.side.setVisible(not self.side.isVisible())
    def toggle_out(self):
        self.out_dock.setVisible(not self.out_dock.isVisible())

def main():
    import sys
    app = QApplication(sys.argv)
    w = App()
    w.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
