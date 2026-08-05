# app.py —— Simply Token 节点图编辑器（NodeGraphQt 轮子版）
# 节点显示/缩放/平移/连线/右键菜单全用 NodeGraphQt 库；数据/VM/补全/网络/存取逻辑不变
import copy, json, os, random, struct
from PySide6.QtWidgets import (QApplication, QMainWindow, QDockWidget, QListWidget,
    QToolBar, QMenu, QLabel, QTextEdit, QLineEdit, QDialog, QFormLayout, QHBoxLayout,
    QVBoxLayout, QPushButton, QDialogButtonBox, QInputDialog, QListWidgetItem)
from PySide6.QtCore import Qt, QTimer, QStringListModel
from PySide6.QtGui import QAction
from NodeGraphQt import NodeGraph, BaseNode, NodeBaseWidget
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

# ---------- 数据模型 ----------
def new_node(name, data="", x=0.0, y=0.0):
    return {"name": name, "data": data, "x": x, "y": y, "children": [], "collapsed": False}

def wrap_block(title, tokens, x=40.0, y=40.0):
    blk = new_node(title, "", x, y)
    for i, (nm, dt) in enumerate(tokens):
        blk["children"].append(new_node(nm, dt, x + 20, y + (i + 1) * 60))
    return blk


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

# ---------- 迷你 VM（与旧版一致，input 可注入） ----------
class VM:
    """树形 VM：层级推进自动压返回标记，块结束/ret 自动弹标记返回上层（参考 Singularity vmstate/vmexec）"""
    # 数据驱动指令表（一行一指令）
    OPS = {
        'int':   lambda v, d: v.vars.setdefault(d, 0),
        'set':   lambda v, d: v.vars.__setitem__(d, v.pop()),
        'read':  lambda v, d: v.stack.append(v.vars.get(d, 0)),
        'inc':   lambda v, d: v.vars.__setitem__(d, v.vars.get(d, 0) + 1),
        'add':   lambda v, d: v.stack.append(v.pop() + v.pop()),
        'sub':   lambda v, d: v.stack.append((lambda a, b: b - a)(v.pop(), v.pop())),
        'mul':   lambda v, d: v.stack.append(v.pop() * v.pop()),
        'div':   lambda v, d: v.stack.append((lambda a, b: b // a if a else 0)(v.pop(), v.pop())),
        'rand':  lambda v, d: v.stack.append(random.randint(1, int(d or 100))),
        'eq':    lambda v, d: v.stack.append(1 if v.pop() == v.pop() else 0),
        'gt':    lambda v, d: v.stack.append((lambda a, b: 1 if b > a else 0)(v.pop(), v.pop())),
        'lt':    lambda v, d: v.stack.append((lambda a, b: 1 if b < a else 0)(v.pop(), v.pop())),
        'print': lambda v, d: v.out(d if d else str(v.pop())),
        'input': lambda v, d: v.stack.append(next(v._inject) if v._inject else v._ask_int()),
        'nop':   lambda v, d: None,
    }

    def __init__(self, out=print):
        self.out = out
        self.reset()
    def reset(self):
        self.vars, self.stack, self.steps, self.depth = {}, [], 0, 0
        self._inject = None
    def pop(self):
        return self.stack.pop() if self.stack else 0
    def run(self, nodes, max_steps=1000, trace=True):
        """nodes: 根节点树（每个节点含 name/data/children）"""
        self.reset()
        stack = [[list(nodes), 0]]          # 调用栈：父帧即返回标记
        while stack and self.steps < max_steps:
            self.steps += 1
            frame = stack[-1]
            lst, idx = frame
            if idx >= len(lst):
                # 层级结束：弹返回标记，自动回上层
                stack.pop()
                if trace and stack:
                    self.out('← 块结束，返回上层（弹返回标记，深度 %d）' % len(stack))
                continue
            node = lst[idx]
            frame[1] = idx + 1
            name, data = node['name'], node['data']
            if node.get('children'):
                # 层级推进：压返回标记（父帧已记好下一位置）
                stack.append([list(node['children']), 0])
                self.depth = max(self.depth, len(stack))
                if trace:
                    self.out('→ 进入 %s（压返回标记，深度 %d）' % (name or '块', len(stack)))
                continue
            act = self.exec(name, data, stack)
            if act == 'end':
                stack.clear()
            elif act == 'ret':
                if trace:
                    self.out('← ret 返回（弹返回标记，深度 %d）' % max(1, len(stack) - 1))
                stack.pop()
        if self.steps >= max_steps:
            self.out('(达到步数上限，已停止)')
    def _find(self, target, nodes):
        """在当前层节点里找标签"""
        for i, n in enumerate(nodes):
            if n['name'] == target:
                return i
        return -1
    def exec(self, name, data, stack):
        fn = self.OPS.get(name)
        if fn: return fn(self, data)
        if name == 'ifz':
            if self.pop() == 0: self._jump(data, stack)
        elif name == 'jmp': self._jump(data, stack)
        elif name == 'ret': return 'ret' if len(stack) > 1 else 'end'
        elif name == 'end': return 'end'
        return None
    def _jump(self, target, stack):
        i = self._find(target, stack[-1][0])
        if i >= 0: stack[-1][1] = i
        else: self.out('(跳转目标不存在: ' + target + ')')
    def _ask_int(self):
        val, ok = QInputDialog.getInt(None, '输入', '请输入数字')
        return val if ok else 0

def collect_completions(nodes):
    """补全来源：零大小 data 节点（data==''）的名字；优先级=父data优先级×位置×大小"""
    prios = {}
    def walk(ns, parent_prio):
        for i, n in enumerate(ns):
            pos = i + 1
            data = n.get('data', '')
            psize = len(data.encode('utf-8')) if data else 0
            child_prio = parent_prio * pos * max(1, psize)   # 父data优先级 × 位置 × 大小
            if data == '' and n.get('name'):
                prios[n['name']] = max(prios.get(n['name'], 0), child_prio)
            if n.get('children'):
                walk(n['children'], child_prio)
    walk(nodes, 1.0)
    if not prios:
        return list(BASE_TOKENS)      # 文档无零大小data时退回基础表
    return [k for k, _ in sorted(prios.items(), key=lambda x: -x[1])]

class CompleteLineEdit(QLineEdit):
    """输入补全：QCompleter 轮子（弹窗跟随光标/上下键/回车/Esc 全内置）+ 预过滤 + 空格插入"""
    def __init__(self, text='', source=None):
        super().__init__(text)
        self._source = source or (lambda: BASE_TOKENS)
        self._model = QStringListModel(self)
        self._comp = QCompleter(self._model, self)
        self._comp.setCaseSensitivity(Qt.CaseInsensitive)
        self._comp.setCompletionMode(QCompleter.PopupCompletion)
        self.setCompleter(self._comp)
        self.textChanged.connect(self._refresh)
    def _refresh(self, q):
        if not q:
            self._comp.popup().hide(); return
        # 预过滤（prefix_ci_us 忽略下划线+大小写），优先级顺序保留，QCompleter 只负责弹窗
        self._model.setStringList([n for n in self._source() if prefix_ci_us(n, q)][:64])
        self._comp.complete()
    def keyPressEvent(self, e):
        # 空格插入当前补全
        if e.key() == Qt.Key_Space and self._comp.popup().isVisible():
            txt = self._comp.currentCompletion()
            if txt:
                self.setText(txt)
                self.setCursorPosition(len(txt))
                return
        super().keyPressEvent(e)


# ---------- NodeGraphQt 节点（库渲染，零手写绘制） ----------
class NodeListWidget(NodeBaseWidget):
    """把 QListWidget 包装成 NodeGraphQt 可挂载的节点部件"""
    def __init__(self, parent=None):
        super().__init__(parent, "children")
        self._widget = QListWidget()
        self.set_custom_widget(self._widget)
    def get_value(self): return ""
    def set_value(self, text): pass
    def list_widget(self): return self._widget

class TokNode(BaseNode):
    """每个 token/块 = 一个图节点；块动态挂子 token 列表（库渲染，零手写绘制）"""
    __identifier__ = "simply"
    NODE_NAME = "token"
    def __init__(self):
        super().__init__()
        self._node = None            # 反向引用 dict 节点
        self._app = None
        self._kids = None            # 块节点才有
        self.add_input("in")
        self.add_output("out")
        self.add_text_input("data", "data", tab="内容")
    def refresh_kids(self):
        if self._kids is None or self._node is None: return
        lw = self._kids.list_widget()
        lw.clear()
        for c in sorted(self._node.get("children", []), key=lambda x: (x["y"], id(x))):
            it = QListWidgetItem("  " + c["name"] + ("  |  " + c["data"] if c["data"] else ""))
            it.setData(Qt.UserRole, c)
            lw.addItem(it)
        lw.itemDoubleClicked.connect(lambda it: self._app and self._app.edit_token(it.data(Qt.UserRole)))

STATE = "app_state.json"          # 本地布局保存

# ---------- 主窗口（NodeGraphQt 轮子） ----------
class App(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Simply Token 节点图编辑器（NodeGraphQt）")
        self.resize(1280, 800)
        self.nodes, self.key = [], b""
        self.dirty, self.undo_stack = False, []
        self.vm = VM()
        self.graph = NodeGraph()
        self.graph.register_node(TokNode)
        self.view = self.graph.widget
        self._items = {}
        self.graph.node_double_clicked.connect(self._on_double_click)
        self.graph.nodes_deleted.connect(self._on_nodes_deleted)
        self.build_ui()
        self.load()
        self.refresh_graph()
        QTimer.singleShot(3000, self.after_loop)

    def build_ui(self):
        bar = QToolBar(); bar.setMovable(False); self.addToolBar(bar)
        def act(t, fn):
            a = QAction(t, self); a.triggered.connect(fn); bar.addAction(a); return a
        act("保存", self.save); act("运行", self.run)
        m = QMenu(self)
        addm = m.addMenu("添加")
        for label, names in [("变量", ["int", "set", "read", "inc"]),
                             ("运算", ["add", "sub", "mul", "div", "rand", "eq", "gt", "lt"]),
                             ("控制", ["ifz", "jmp", "ret", "end", "nop"]),
                             ("交互", ["print", "input"]),
                             ("标签", ["main", "notwin", "loop", "exit"]),
                             ("网络", ["net"])]:
            sub = addm.addMenu(label)
            for nm in names:
                sub.addAction(nm, lambda k=nm: self.add_node(k))
        addm.addAction("新建块", self.add_block)
        for t, fn in [("加载", self.load), ("载入猜数字示例", self.load_template),
                      ("自动布局", self.auto_layout), ("撤销", self.undo),
                      ("快速添加 token（补全）", self.quick_add_token),
                      ("服务器查看器", self.toggle_side), ("输出面板", self.toggle_out)]:
            m.addAction(t, fn)
        bar.addAction("\u2630", m.popup)
        self.status = QLabel(""); bar.addWidget(self.status)

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

    # ---------- 场景（NodeGraphQt：建节点/连线/删除全内置） ----------
    def refresh_graph(self):
        g = self.graph
        for n in list(g.all_nodes()):
            g.delete_node(n)
        self._items = {}
        for n in self.nodes:
            tn = g.create_node("simply.TokNode", name=n["name"])
            tn._node = n; tn._app = self
            tn.set_property("data", n["data"])
            tn.set_pos(n["x"], n["y"])
            if n.get("children") and tn._kids is None:
                tn._kids = NodeListWidget()
                tn.add_custom_widget(tn._kids, "children", tab="内容")
            tn.refresh_kids()
            self._items[id(n)] = tn
        roots = sorted(self.nodes, key=lambda x: (x["y"], id(x)))
        for i in range(len(roots) - 1):
            self._items[id(roots[i])].output(0).connect_to(self._items[id(roots[i + 1])].input(0))
        self.status.setText("%d 根 / %d token | %s" % (len(self.nodes), len(ordered(self.nodes)),
                             "未保存" if self.dirty else ""))

    def sync_positions(self):
        for n, tn in self._items.items():
            try: n["x"], n["y"] = tn.pos()
            except Exception: pass

    def _on_double_click(self, node):
        n = getattr(node, "_node", None)
        if n is None: return
        if n.get("children"): self.edit_block(n)
        else: self.edit_token(n)

    def _on_nodes_deleted(self, nodes):
        removed = {id(getattr(n, "_node", None)) for n in nodes if getattr(n, "_node", None)}
        if not removed: return
        self.snapshot()
        self.nodes = [n for n in self.nodes if id(n) not in removed]
        for n in self.nodes:
            n["children"] = [c for c in n.get("children", []) if id(c) not in removed]
        self.dirty = True; self.refresh_graph()

    # ---------- 布局 ----------
    def auto_layout(self):
        if not self.nodes: return
        self.snapshot()
        y = 40.0
        for i, n in enumerate(sorted(self.nodes, key=lambda x: (x["y"], id(x)))):
            n["x"] = 60.0 + (i % 4) * 360
            n["y"] = y
            y += 60 + len(n.get("children", [])) * 26
        self.refresh_graph()

    def edit_token(self, node):
        d = QDialog(self); d.setWindowTitle("编辑 token")
        f = QFormLayout(d)
        e1 = CompleteLineEdit(node["name"], lambda: collect_completions(self.nodes))
        e2 = QLineEdit(node["data"])
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
        # 轮子：QInputDialog 单行输入
        name, ok = QInputDialog.getText(self, "编辑块", "块名", text=node["name"])
        if ok and name.strip():
            self.snapshot()
            node["name"] = name.strip() or "块"
            self.dirty = True; self.refresh_graph()

    def quick_add_token(self, parent=None):
        d = QDialog(self); d.setWindowTitle("快速添加 token（补全）")
        lay = QVBoxLayout(d)
        e = CompleteLineEdit("", lambda: collect_completions(self.nodes))
        e.setPlaceholderText("输入前缀，空格/回车补全插入")
        lay.addWidget(e)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(d.accept); bb.rejected.connect(d.reject)
        lay.addWidget(bb)
        e.setFocus()
        if d.exec() == QDialog.Accepted:
            name = e.text().strip()
            if name: self.add_node(name, "", parent=parent)

    def net_dialog(self, node):
        """网络节点：查看/浏览服务器 key（QListWidgetItem+UserRole 存结构化数据）"""
        d = QDialog(self); d.setWindowTitle("网络节点 - 查看服务器"); d.resize(600, 440)
        lay = QVBoxLayout(d)
        row = QHBoxLayout(); row.addWidget(QLabel("key:"))
        ekey = QLineEdit(node.get("data", "")); ekey.setPlaceholderText("key（留空 = 零data 空key）")
        row.addWidget(ekey, 1); lay.addLayout(row)
        lb = QListWidget(); lay.addWidget(lb, 1)
        status = QLabel(""); status.setStyleSheet("color:#8fa3c8;"); lay.addWidget(status)
        def add(txt, payload=None):
            it = QListWidgetItem(txt)
            if payload is not None: it.setData(Qt.UserRole, payload)
            lb.addItem(it)
        def refresh():
            lb.clear()
            k = ekey.text().encode("utf-8")
            try:
                toks = decode(boot_dll.fetch(k)) if k else []
                if not toks: add("(空块)")
                for nm, dt in toks:
                    add(nm + ("  |  " + dt if dt else ""), ("tok", nm, dt))
                status.setText("已取回 %d 个 token" % len(toks))
            except Exception:
                add("(服务器无此 key 的数据)"); status.setText("key 无数据")
        def browse():
            lb.clear()
            try:
                keys = boot_dll.list_keys()
                if not keys: add("(服务器为空)")
                for k, c in keys:
                    add("[%d条] %s" % (c, k.decode("utf-8", "replace") or "<空 key>"),
                        ("key", k.decode("utf-8", "replace")))
                status.setText("共 %d 个 key" % len(keys))
            except Exception as ex:
                status.setText("浏览失败: %s" % ex)
        def use_selected():
            it = lb.currentItem()
            if not it: return
            p = it.data(Qt.UserRole)
            ekey.setText(p[1] if p else it.text())
            refresh()
        def load_into_editor():
            k = ekey.text().encode("utf-8")
            try:
                toks = decode(boot_dll.fetch(k)) if k else []
                if not toks: status.setText("空块，无法载入"); return
                self.snapshot()
                c = (100.0, 100.0)
                for i, (nm, dt) in enumerate(toks):
                    self.nodes.append(new_node(nm, dt, c.x() + (i % 6) * 30, c.y() + (i // 6) * 30))
                node["data"] = ekey.text(); self.dirty = True; self.refresh_graph()
                status.setText("已载入 %d 个 token 到编辑器" % len(toks))
            except Exception:
                status.setText("载入失败：服务器无此 key")
        def setkey():
            node["data"] = ekey.text(); status.setText("已设为节点 key")
        btns = QHBoxLayout()
        for t, fn in [("刷新", refresh), ("浏览服务器", browse), ("使用选中", use_selected),
                      ("载入编辑器", load_into_editor), ("设为节点key", setkey), ("关闭", d.accept)]:
            b = QPushButton(t); b.clicked.connect(fn); btns.addWidget(b)
        lay.addLayout(btns)
        d.exec()

    def snapshot(self):
        self.undo_stack.append(copy.deepcopy(self.nodes))
        if len(self.undo_stack) > 60: self.undo_stack.pop(0)

    def undo(self):
        if self.undo_stack:
            self.nodes = self.undo_stack.pop()
            self.dirty = True; self.refresh_graph()

    def add_node(self, name, data="", parent=None):
        self.snapshot()
        c = (120.0 + len(self.nodes) * 30, 120.0 + len(self.nodes) * 30)
        node = new_node(name, data, c[0], c[1])
        if parent is not None:
            parent["children"].append(node); parent["collapsed"] = False
        else:
            self.nodes.append(node)
        self.dirty = True; self.refresh_graph()

    def add_block(self):
        self.add_node("块")

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
                it = QListWidgetItem("   " + nm + ("  |  " + dt if dt else ""))
                it.setData(Qt.UserRole, (nm, dt))
                self.listw.addItem(it)
        self.listw.addItem("---- %d 组 ----" % len(self.viewer_groups()))

    def viewer_add(self):
        it = self.listw.currentItem()
        p = it.data(Qt.UserRole) if it else None
        if p:
            self.add_node(*p)

    # ---------- 布局 ----------

    def load_template(self):
        self.snapshot()
        self.nodes = [wrap_block("猜数字", guess_template())]
        self.dirty = True
        self.refresh_graph(); self.fit()
        self.status.setText("已载入猜数字示例：1 块 / %d token" % len(guess_template()))

    # ---------- 服务器存取 ----------

    def save(self):
        self.sync_positions()
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

    def run(self, nodes, max_steps=1000, trace=True):
        """nodes: 根节点树（每个节点含 name/data/children）"""
        self.reset()
        stack = [[list(nodes), 0]]          # 调用栈：父帧即返回标记
        while stack and self.steps < max_steps:
            self.steps += 1
            frame = stack[-1]
            lst, idx = frame
            if idx >= len(lst):
                # 层级结束：弹返回标记，自动回上层
                stack.pop()
                if trace and stack:
                    self.out('← 块结束，返回上层（弹返回标记，深度 %d）' % len(stack))
                continue
            node = lst[idx]
            frame[1] = idx + 1
            name, data = node['name'], node['data']
            if node.get('children'):
                # 层级推进：压返回标记（父帧已记好下一位置）
                stack.append([list(node['children']), 0])
                self.depth = max(self.depth, len(stack))
                if trace:
                    self.out('→ 进入 %s（压返回标记，深度 %d）' % (name or '块', len(stack)))
                continue
            act = self.exec(name, data, stack)
            if act == 'end':
                stack.clear()
            elif act == 'ret':
                if trace:
                    self.out('← ret 返回（弹返回标记，深度 %d）' % max(1, len(stack) - 1))
                stack.pop()
        if self.steps >= max_steps:
            self.out('(达到步数上限，已停止)')

    def toggle_side(self):
        self.side.setVisible(not self.side.isVisible())

    def toggle_out(self):
        self.out_dock.setVisible(not self.out_dock.isVisible())

def main():
    import sys, ctypes
    app = QApplication(sys.argv)
    w = App()
    w.show()
    # Qt6 在部分环境下 show() 不设置 WS_VISIBLE，强制显示（tkinter 无此问题）
    try:
        hwnd = int(w.winId())
        ctypes.windll.user32.ShowWindow(hwnd, 5)      # SW_SHOW
        ctypes.windll.user32.SetForegroundWindow(hwnd)
    except Exception:
        pass
    sys.exit(app.exec())

if __name__ == "__main__":
    main()


def main():
    import sys, ctypes
    app = QApplication(sys.argv)
    w = App()
    w.show()
    # Qt6 部分环境下 show() 不设 WS_VISIBLE，强制显示
    try:
        hwnd = int(w.winId())
        ctypes.windll.user32.ShowWindow(hwnd, 5)
        ctypes.windll.user32.SetForegroundWindow(hwnd)
    except Exception:
        pass
    sys.exit(app.exec())

if __name__ == "__main__":
    main()