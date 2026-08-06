# app_pyglet.py —— Simply 高上限节点图编辑器（pyglet 版，参考 transition draw_block）
# 交互: 右键拖拽=移动 | 滚轮=缩放 | 左键单击行=编辑/进入net | 标题+/-=折叠 | Ctrl+S 保存
import json, os, struct, sys, binascii
import pyglet
from pyglet.graphics import Batch
from pyglet.shapes import Rectangle, Line
from pyglet.window import mouse, key
from pyglet.math import Mat4, Vec3

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import boot_dll

W, H = 1280, 800
ROW_H, TITLE_H, CARD_W = 24, 30, 340
BG = (15, 18, 24)
CAT = {"read":(200,224,160),"set":(232,200,120),"int":(127,184,216),
       "add":(94,200,232),"sub":(94,200,232),"mul":(94,200,232),"div":(94,200,232),
       "inc":(94,200,232),"nop":(94,200,232),"jmp":(94,200,232),"print":(94,200,232),
       "eq":(208,128,224),"gt":(208,128,224),"lt":(208,128,224),"ifz":(208,128,224),
       "input":(224,160,80),"net":(247,118,142),"end":(255,158,100)}
GREEN=(98,201,130); TITLE_C=(157,167,179); CARD_BG=(32,38,60); HEAD=(40,48,70)
TEXT_C=(232,236,239); DIM=(102,113,125); EDGE=(52,65,77)

def cat_color(n): return CAT.get(n, (115,218,202))

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

def crc_name(key):
    data = key.encode() if isinstance(key, str) else key
    n = binascii.crc32(data) & 0xFFFFFFFF
    if n == 0: return "A"
    ch = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567"
    out = []
    while n:
        out.append(ch[n % 32]); n //= 32
    return "".join(reversed(out))

def node(nm, d="", x=0.0, y=0.0, kids=None):
    return {"name": nm, "data": d, "x": x, "y": y, "children": kids or [], "collapsed": False}

def default_net_node(px=520, py=100):
    """默认网络节点：零大小 data → 打开空 key 的块（引导块），只读"""
    try:
        toks = decode(boot_dll.fetch(b""))
        if not toks: return None
        nb = {"kind": "net", "net_key": b"", "name": "", "data": "",
              "x": px, "y": py, "collapsed": False}
        nb["children"] = [node(nm, dt, 0, i*ROW_H) for i, (nm, dt) in enumerate(toks)]
        for c in nb["children"]: c["_ro"] = True
        return nb
    except Exception:
        return None

def ordered(ns):
    out = []
    def vis(n):
        out.append(n)
        for c in sorted(n.get("children", []), key=lambda x: (x["y"], id(x))): vis(c)
    for n in sorted(ns, key=lambda x: (x["y"], id(x))): vis(n)
    return out

def flatten(ns): return [(n["name"], n["data"]) for n in ordered(ns)]

def _with_net(nodes):
    """启动时始终附带一个默认网络节点（零大小 data → 空 key 引导块）"""
    net = default_net_node()
    return nodes + ([net] if net else [])

def load_block():
    bf = sys.argv[1] if len(sys.argv) > 1 else None
    kf = sys.argv[2] if len(sys.argv) > 2 else None
    if bf and os.path.exists(bf):
        toks = decode(open(bf, "rb").read())
        if toks:
            blk = node("当前块", "", 100, 100)
            blk["children"] = [node(nm, dt, 0, i * ROW_H) for i, (nm, dt) in enumerate(toks)]
            try:
                blk["key"] = bytes.fromhex(open(kf).read().strip()) if kf and os.path.exists(kf) else None
            except Exception:
                blk["key"] = None
            return _with_net([blk])
    try:
        key = boot_dll.get_id()
        toks = decode(boot_dll.fetch(key))
        if toks:
            blk = node("当前块", "", 100, 100)
            blk["children"] = [node(nm, dt, 0, i * ROW_H) for i, (nm, dt) in enumerate(toks)]
            blk["key"] = key
            return _with_net([blk])
    except Exception:
        pass
    try:
        return _with_net(json.load(open(os.path.join(HERE, "app_state.json"), encoding="utf-8"))["nodes"])
    except Exception:
        return _with_net([node("空块", "", 100, 100)])

class Editor:
    def __init__(self):
        self.nodes = load_block()
        self.cam = [0.0, 0.0, 1.0]
        self.drag = None
        self.edit = None
        self.edit_buf = ""
        self.win = pyglet.window.Window(W, H, "Simply pyglet 编辑器")
        self.win.push_handlers(self)
        self.fps = pyglet.window.FPSDisplay(self.win)

    def block_h(self, b):
        return TITLE_H + (0 if b.get("collapsed") else len(b["children"])) * ROW_H + 8

    def label(self, text, x, y, color, bold=False, size=10):
        col = (color[0], color[1], color[2], 255)
        l = pyglet.text.Label(text, x=x, y=y, font_name="Microsoft YaHei UI",
                              font_size=size, color=col)
        self.texts.append(l)

    def add_block(self, b):          # 块节点：编辑本地块（深色卡片）
        x, y = b["x"], b["y"]
        h = self.block_h(b)
        Rectangle(x, y, CARD_W, h, color=CARD_BG, batch=self.batch)
        Rectangle(x, y, CARD_W, TITLE_H, color=HEAD, batch=self.batch)
        Line(x, y+TITLE_H, x+CARD_W, y+TITLE_H, thickness=1, color=EDGE, batch=self.batch)
        Rectangle(x+CARD_W-26, y+7, 16, 16, color=(38,49,77), batch=self.batch)
        t = b["name"] or "块"
        if b.get("key") is not None:
            t += "  [" + crc_name(b["key"]) + "]"
        self.label(t, x+10, y+5, TITLE_C, bold=True, size=11)
        self.label("-" if not b.get("collapsed") else "+", x+CARD_W-23, y+6, TEXT_C, bold=True, size=10)
        if b.get("collapsed"):
            self.label("%d tokens" % len(b["children"]), x+10, y+h-22, DIM, size=9)
            return
        for i, c in enumerate(b["children"]):
            y0 = y + TITLE_H + i * ROW_H
            col = cat_color(c["name"])
            Rectangle(x+8, y0+5, 12, 14, color=col, batch=self.batch)
            self.label(c["name"], x+26, y0+4, col, size=10)
            if c["name"] == "net":
                summ = crc_name(c["data"]) if c["data"] else "A"   # 零 data → crc=0 → "A"
                self.label("| " + summ, x+150, y0+4, TEXT_C, size=9)
            elif c["data"]:
                self.label("| " + c["data"], x+150, y0+4, TEXT_C, size=9)
            Line(x+4, y0+ROW_H, x+CARD_W-4, y0+ROW_H, thickness=1, color=(26,32,44), batch=self.batch)

    def add_net_node(self, b):       # 网络节点：只读显示远程块（独立样式）
        x, y = b["x"], b["y"]
        h = self.block_h(b)
        Rectangle(x, y, CARD_W, h, color=(24,42,58), batch=self.batch)          # 网络底色
        Rectangle(x, y, CARD_W, TITLE_H, color=(32,70,95), batch=self.batch)    # 网络标题栏
        Line(x, y+TITLE_H, x+CARD_W, y+TITLE_H, thickness=1, color=(70,140,170), batch=self.batch)
        Rectangle(x+CARD_W-26, y+7, 16, 16, color=(38,70,90), batch=self.batch)
        # 网络图标（小圆点）
        Rectangle(x+10, y+10, 8, 8, color=(98,201,130), batch=self.batch)
        # 标题：网络 + crc 短名
        self.label("网络 " + crc_name(b["net_key"]), x+24, y+5, (150,220,240), bold=True, size=11)
        if b["net_key"] == b"": self.label("(零data/空key)", x+24, y+22, (102,150,180), size=8)
        self.label("-" if not b.get("collapsed") else "+", x+CARD_W-23, y+6, TEXT_C, bold=True, size=10)
        if b.get("collapsed"):
            self.label("%d tokens" % len(b["children"]), x+10, y+h-22, DIM, size=9)
            return
        for i, c in enumerate(b["children"]):
            y0 = y + TITLE_H + i * ROW_H
            col = cat_color(c["name"])
            Rectangle(x+8, y0+5, 12, 14, color=col, batch=self.batch)
            self.label(c["name"], x+26, y0+4, col, size=10)
            if c["data"]:
                self.label("| " + c["data"], x+150, y0+4, TEXT_C, size=9)
            Line(x+4, y0+ROW_H, x+CARD_W-4, y0+ROW_H, thickness=1, color=(26,42,58), batch=self.batch)

    def link_blocks(self):
        r = sorted(self.nodes, key=lambda x: x["y"])
        for i in range(len(r)-1):
            a, b2 = r[i], r[i+1]
            Line(a["x"]+CARD_W, a["y"]+self.block_h(a)//2,
                 b2["x"], b2["y"]+self.block_h(b2)//2, thickness=2, color=GREEN, batch=self.batch)

    def on_draw(self):
        with open(os.path.join(HERE, "_pyglet_draw.log"), "a", encoding="utf-8") as _f:
            _f.write("draw\n")
        try:
            import pyglet.gl as _gl
            _gl.glClearColor(BG[0]/255, BG[1]/255, BG[2]/255, 1)
            self.win.clear()
            s = self.cam[2]
            self.win.view = Mat4.from_translation(Vec3(self.cam[0], self.cam[1], 0)) @ Mat4.from_scale(Vec3(s, s, 1))
            self.batch = Batch()
            self.texts = []
            for b in self.nodes:
                if b.get("kind") == "net":
                    self.add_net_node(b)          # 网络节点（独立）
                else:
                    self.add_block(b)             # 块节点
            self.link_blocks()
            self.batch.draw()
            for l in self.texts:
                l.draw()
            self.fps.draw()
        except Exception:
            import traceback
            with open(os.path.join(HERE, "_pyglet_err.log"), "a", encoding="utf-8") as _f:
                _f.write(traceback.format_exc() + "\n")

    def screen_to_world(self, x, y):
        s = self.cam[2]
        return ((x - W/2 - self.cam[0]) / s + W/2, (y - H/2 - self.cam[1]) / s + H/2)

    def hit_block(self, x, y):
        for b in self.nodes:
            h = self.block_h(b)
            if b["x"] <= x <= b["x"]+CARD_W and b["y"] <= y <= b["y"]+h:
                return b
        return None

    def hit_row(self, b, x, y):
        if b.get("collapsed"): return -1
        r = int((y - b["y"] - TITLE_H) // ROW_H)
        return r if 0 <= r < len(b["children"]) else -1

    def on_mouse_press(self, x, y, button, mods):
        wx, wy = self.screen_to_world(x, y)
        b = self.hit_block(wx, wy)
        if not b: return
        if button == mouse.RIGHT:
            self.drag = (b, wx - b["x"], wy - b["y"])
        elif button == mouse.LEFT:
            if b["y"]+7 <= wy <= b["y"]+23 and b["x"]+CARD_W-26 <= wx <= b["x"]+CARD_W-10:
                b["collapsed"] = not b.get("collapsed"); return
            r = self.hit_row(b, wx, wy)
            if r >= 0:
                c = b["children"][r]
                if c["name"] == "net":
                    self.enter_net(c["data"], b)   # data 空 → 默认打开零大小 data 的块
                else:
                    self.start_edit(b, r, c)
            elif wy <= b["y"] + TITLE_H:
                if b.get("kind") == "net":
                    self.refresh_net(b)              # 网络节点：刷新远程数据
                else:
                    self.start_edit(b, -1, b)        # 块节点：编辑块名

    def on_mouse_drag(self, x, y, dx, dy, bt, mods):
        if self.drag and (bt & mouse.RIGHT):
            b, ox, oy = self.drag
            wx, wy = self.screen_to_world(x, y)
            b["x"], b["y"] = wx - ox, wy - oy
        if bt & mouse.MIDDLE:
            self.cam[0] += dx; self.cam[1] += dy

    def on_mouse_scroll(self, x, y, sx, sy):
        self.cam[2] *= 1.1 if sy > 0 else 0.9
        self.cam[2] = max(0.05, min(20, self.cam[2]))

    def on_key_press(self, symbol, mods):
        if symbol == key.ESCAPE:
            self.edit = None; self.edit_buf = ""
        elif self.edit and symbol == key.ENTER:
            self.commit_edit()
        elif symbol == key.S and mods & key.MOD_CTRL:
            self.save()

    def on_text(self, text):
        if self.edit:
            self.edit_buf += text

    def start_edit(self, b, r, c):
        if c.get("_ro"):
            print("（网络数据只读，双击标题刷新）")
            return
        self.edit = (b, r)
        self.edit_buf = c["name"] if r == -1 else c["data"]

    def commit_edit(self):
        b, r = self.edit
        if r == -1:
            b["name"] = self.edit_buf or "块"
        else:
            b["children"][r]["data"] = self.edit_buf
        self.edit = None; self.edit_buf = ""

    def enter_net(self, key_s, parent):
        """网络节点（独立类型）：fetch(key) → kind='net' 只读节点。
        key_s 为空（零大小 data）时默认打开空 key 的块（引导块）。"""
        try:
            key = key_s.encode() if key_s else b""      # 零大小 data → 空 key
            toks = decode(boot_dll.fetch(key))
            if not toks: return
            nb = {"kind": "net", "net_key": key, "name": "", "data": "",
                  "x": parent["x"]+CARD_W+60, "y": parent["y"], "collapsed": False}
            nb["children"] = [node(nm, dt, 0, i*ROW_H) for i, (nm, dt) in enumerate(toks)]
            for c in nb["children"]: c["_ro"] = True
            self.nodes.append(nb)
        except Exception:
            pass

    def refresh_net(self, b):
        try:
            k = b["net_key"]
            k = k.encode() if isinstance(k, str) else k
            toks = decode(boot_dll.fetch(k))
            if not toks: return
            b["children"] = [node(nm, dt, 0, i*ROW_H) for i, (nm, dt) in enumerate(toks)]
            for c in b["children"]: c["_ro"] = True
        except Exception:
            pass

    def save(self):
        try:
            b = self.nodes[0]
            key = b.get("key")
            if key is None:
                key = boot_dll.get_id()
            payload = encode(flatten(self.nodes))
            idx = boot_dll.upload(key, payload)
            json.dump({"nodes": self.nodes}, open(os.path.join(HERE, "app_state.json"), "w", encoding="utf-8"), ensure_ascii=False)
            print("已保存 idx=%d（%d token）" % (idx, len(flatten(self.nodes))))
        except Exception as e:
            print("保存失败:", e)

if __name__ == "__main__":
    ed = Editor()
    def _tick(dt):
        ed.on_draw()
    pyglet.clock.schedule_interval(_tick, 1/60)   # 持续渲染（事件驱动窗口无事件不重绘）
    pyglet.app.run()
