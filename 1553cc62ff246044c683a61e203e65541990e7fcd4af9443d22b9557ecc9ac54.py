# editor 插件：token 流编辑器（纵向行布局）
# 空格=插入补全token | Ctrl=cond Ctrl+Alt=handrun Shift+Ctrl=condrerun | 右键拖出重排
# read/set 贴指令左右；命中/未命中颜色；cond/handrun/condrerun 热力高亮+悬浮编辑+handrun按钮
# 中键平移+滚轮缩放；补全跟随鼠标（零大小data，优先度=父优先度×排名×大小）
import inspect, struct, binascii, hashlib, os
from block import fetch, HOST, PORT, HERE
import socket, pyglet, ctypes
from pyglet.shapes import Circle, Line
from pyglet.window import mouse, key
from pyglet.math import Mat4, Vec3

W, H, RH, GAP = 960, 640, 30, 8          # 窗口/行高/行距
BG, CARD, DIM, TXT = (15,18,24), (32,38,60), (70,80,90), (232,236,239)
GREEN, YELLOW, BLUE = (98,201,130), (232,200,120), (127,184,216)
COND, HAND, CRUN = (208,128,224), (247,118,142), (255,158,100)   # cond/handrun/condrerun 基色
HOT, HIT = (255,80,80), (90,160,220)     # 热力/命中

# —— 定位 editor 所在块 ——
key_ = b""
for f in inspect.stack()[1:]:
    if f.function == "run_loop":
        key_ = f.frame.f_locals.get("start_key", b""); break

# —— 块 = [(name, payload)] ——
def tokens(blk):
    out, i = [], 0
    while i + 4 <= len(blk):
        n = struct.unpack_from("<I", blk, i)[0]; i += 4
        if not n: break
        name = blk[i:i+n].decode("utf-8","replace"); i += n
        d = struct.unpack_from("<I", blk, i)[0]; i += 4
        out.append((name, blk[i:i+d].decode("utf-8","replace"))); i += d
    return out

def plugin_exists(name):
    return os.path.exists(os.path.join(HERE, hashlib.sha256(name.encode()).hexdigest()+".py"))

# —— handrun payload: 8字节id + 目标token；布尔由 id 索引 ——
hand_flags = {}                           # id(bytes) -> [b1, b2]
def split_handrun(p):
    return p[8:].decode("utf-8","replace"), p[:8] if len(p) >= 8 else b""
def make_handrun(token):
    return os.urandom(8) + token.encode()

# —— 布局：普通 token 一行；read 左贴、set 右贴 ——
def build_lines(toks):
    lines, left = [], []
    for i, (n, p) in enumerate(toks):
        if n == "read": left.append((i, n, p))
        elif n == "set":
            (lines[-1].setdefault("right", []).append((i, n, p)) if lines else left.append((i, n, p)))
        else:
            lines.append({"left": left, "name": (i, n, p), "right": []}); left = []
    if left: lines.append({"left": left, "name": None, "right": []})
    return lines

def crc_name(d):
    n = binascii.crc32(d if isinstance(d,bytes) else d.encode()) & 0xFFFFFFFF
    if not n: return "A"
    s = ""
    while n: s = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567"[n%32] + s; n //= 32
    return s

# —— 补全候选：零大小 data（空 key）递归收集 ——
def try_fetch(key, t=1.0):
    with socket.create_connection((HOST, PORT), timeout=t) as s:
        s.sendall(b"\x02" + struct.pack("<I", len(key)) + key)
        s.settimeout(t)
        n = struct.unpack("<I", s.recv(4))[0]
        d = b""
        while len(d) < n:
            c = s.recv(n - len(d))
            if not c: raise ConnectionError
            d += c
        return d

def collect(key=b"", prio=1.0, depth=0):
    try: ts = tokens(try_fetch(key))
    except Exception: return []
    out = []
    for i, (t, _) in enumerate(ts):
        p = prio * (i+1) * len(t)
        out.append((t, p))
        if depth < 3: out += collect(t.encode(), p, depth+1)
    return out

cands = sorted(collect(), key=lambda c: c[1])
toks = tokens(fetch(key_))                # 本地可编辑 [(name, payload)]
win = pyglet.window.Window(W, H, caption="SelfEdit (editor 所在块)")
cam = [0., 0., 1.]
inp, edit_i, edit_buf = "", -1, ""
mpos = (W/2, H/2)
drag_pos = (0.0, 0.0)                # 右键拖出的鼠标世界坐标                # 当前鼠标位置（窗口坐标）
drag_i, drag_x = -1, 0.0                  # 右键拖出
heat = {}                                 # 热力：cond/handrun/condrerun 执行计数

def label(n, p):
    if n == "handrun": return split_handrun(p)[0] or "handrun"   # 只显示目标 token（str）
    return p if n in ("read","set","cond","condrerun") and p else (n or "?")
def item_w(n, p):
    lb = label(n, p)
    return len(lb)*9 + 20 + (26 if n == "handrun" else 0)   # handrun 加按钮宽

def item_color(n):                        # 命中/未命中 + 特殊类
    if n == "read": return GREEN
    if n == "set": return YELLOW
    if n == "cond": return COND
    if n == "handrun": return HAND
    if n == "condrerun": return CRUN
    return HIT if plugin_exists(n) else DIM     # 命中插件=蓝，未命中=灰

def row_geom(line):
    items, x = [], 0.0
    for it in line["left"]:
        i, n, p = it; items.append(("l", i, n, p, x)); x += item_w(n,p) + 6
    if line["name"]:
        i, n, p = line["name"]; items.append(("n", i, n, p, x)); x += item_w(n,p) + 6
    for it in line["right"]:
        i, n, p = it; items.append(("r", i, n, p, x)); x += item_w(n,p) + 6
    return items, x

def hit(wx, wy):
    row = int(-wy / (RH+GAP))
    lines = build_lines(toks)
    if not (0 <= row < len(lines)): return -1
    for kind, i, n, p, x in row_geom(lines[row])[0]:
        if x <= wx <= x + item_w(n,p): return i
    return -1

def screen_to_world(x, y):
    s = cam[2]
    return ((x - W/2 - cam[0]) / s, (y - H/2 - cam[1]) / s)

def cursor_row():                              # 鼠标在行底之上 → 插该行前
    wx, wy = screen_to_world(*mpos)
    n = len(build_lines(toks))
    for i in range(n):
        if -(i*(RH+GAP)) + RH < wy:        # 行 i 底之上 → 插到该行前
            return i
    return n

def pointer_y():                              # 指针画在行间隙中间（不压文字）
    i = cursor_row()
    n = len(build_lines(toks))
    if i == 0: return RH                   # editor 上方
    if i < n: return -i*(RH+GAP) + (RH+GAP) - GAP/2   # 行 i-1 与行 i 间隙中间（-38i+34）
    return -(n-1)*(RH+GAP) - (RH+GAP)/2    # 末尾下方

# —— 渲染 ——
@win.event
def on_draw():
    import pyglet.gl as gl
    gl.glClearColor(*[c/255 for c in BG], 1); win.clear()
    win.view = Mat4.from_translation(Vec3(cam[0]+W/2, cam[1]+H/2, 0)) @ Mat4.from_scale(Vec3(cam[2], cam[2], 1))
    shapes, labels = [], []
    for row, line in enumerate(build_lines(toks)):
        y = -row * (RH+GAP)
        for kind, i, n, p, x in row_geom(line)[0]:
            if i == drag_i: continue               # 拖出的项单独画
            lb = label(n, p)
            col = item_color(n)                    # 纯文字颜色（无矩形背景）
            if n in ("cond","handrun","condrerun") and heat.get(n):   # 热力：文字偏 HOT
                col = tuple(int(col[j] + (HOT[j]-col[j])*min(heat.get(n,0)*.2,1)) for j in range(3))
            if i == edit_i: col = (255,255,255)    # 悬浮编辑项白字
            labels.append(pyglet.text.Label(lb, x=x+2, y=y+RH/2, font_size=13,
                                            color=col+(255,), anchor_y="center"))
            if n == "handrun":                     # handrun 两个按钮（小圆点）
                _, hid = split_handrun(p)
                f = hand_flags.get(hid, [0, 0])
                for bi in (0, 1):
                    bx = x + item_w(n,p) - 26 + bi*12
                    shapes.append(Circle(bx, y+RH/2, 3, color=(255,200,80) if f[bi] else (70,80,90)))
    # 指针：鼠标位置对应的插入行（参考 transition 的水平线）
    py = pointer_y()
    shapes.append(Line(0, py, 420, py, thickness=2, color=(150,160,170)))
    if drag_i >= 0:                              # 拖出的项跟随鼠标（文字）
        n, p = toks[drag_i]; lb = label(n,p)
        labels.append(pyglet.text.Label(lb, x=drag_pos[0]+2, y=drag_pos[1]+RH/2, font_size=13,
                                        color=(100,160,220)+(255,), anchor_y="center"))
    for s in shapes: s.draw()
    for l in labels: l.draw()
    # —— UI：补全跟随鼠标（pyglet y 向上，鼠标上=候选上）——
    win.view = Mat4()
    mx, my = mpos
    labels = [pyglet.text.Label("> " + inp, x=mx+20, y=my, font_size=14, color=GREEN+(255,))]
    yy = my + 18
    for t, p in cands:
        if t.startswith(inp):
            labels.append(pyglet.text.Label(f"{t}  ({p:.1f})", x=mx+32, y=yy, font_size=11,
                                            color=HIT+(255,) if plugin_exists(t) else DIM+(255,)))
            yy += 17
            if yy > H-20: break
    for l in labels: l.draw()

# —— 交互 ——
@win.event
def on_mouse_drag(x, y, dx, dy, bt, mods):
    global cam, drag_pos
    if bt & mouse.MIDDLE: cam[0]+=dx; cam[1]+=dy
    elif bt & mouse.RIGHT and drag_i >= 0:  # 右键拖出（项跟随鼠标）
        drag_pos = screen_to_world(x, y)

@win.event
def on_mouse_scroll(x, y, sx, sy):
    k = 1.1 if sy>0 else .9; s = cam[2]
    wx, wy = (x-W/2-cam[0])/s, (y-H/2-cam[1])/s
    ns = max(.05, min(20, s*k))
    cam[0], cam[1], cam[2] = x-W/2-wx*ns, y-H/2-wy*ns, ns

def find_item(i):                          # toks 索引 → (行y, 项x, name, payload)
    for row, line in enumerate(build_lines(toks)):
        y = -row * (RH+GAP)
        for kind, ii, n, p, x in row_geom(line)[0]:
            if ii == i: return y, x, n, p
    return None

def insert_pos(wx):                        # 鼠标 x → toks 插入位置（0..len）
    pos = 0
    for line in build_lines(toks):
        for kind, i, n, p, x in row_geom(line)[0]:
            if wx < x + item_w(n,p)/2: return pos
            pos += 1
    return pos

@win.event
def on_mouse_press(x, y, button, mods):
    global drag_i, drag_pos, edit_i
    wx, wy = screen_to_world(x, y)
    if button == mouse.RIGHT:
        drag_i = hit(wx, wy); drag_pos = (wx, wy); edit_i = -1
    elif button == mouse.LEFT:
        i = hit(wx, wy)
        if i >= 0 and toks[i][0] == "handrun":   # 点 handrun 两个按钮（项右端 24px）
            _, hid = split_handrun(toks[i][1])
            fl = hand_flags.setdefault(hid, [0, 0])
            row, xx, nn, pp = find_item(i)
            rel = wx - (xx + item_w(nn,pp) - 24)
            if 0 <= rel < 12: fl[0] = 1 - fl[0]
            elif 12 <= rel < 24: fl[1] = 1 - fl[1]
            hand_flags[hid] = fl
        else:
            edit_i = -1

@win.event
def on_mouse_release(x, y, button, mods):
    global drag_i
    if button == mouse.RIGHT and drag_i >= 0:   # 松手：拖出的项插到鼠标位置
        wx, _ = screen_to_world(x, y)
        item = toks.pop(drag_i)
        toks.insert(insert_pos(wx), item)
        drag_i = -1

@win.event
def on_mouse_motion(x, y, dx, dy):
    global edit_i, mpos
    try:                                   # 鼠标进窗口 → 自动获得键盘焦点（否则收不到按键）
        if ctypes.windll.user32.GetFocus() != win._hwnd:
            ctypes.windll.user32.SetFocus(win._hwnd)
    except Exception:
        pass
    mpos = (x, y)
    wx, wy = screen_to_world(x, y)
    i = hit(wx, wy)
    edit_i = i if (i >= 0 and toks[i][0] in ("read","set","cond","handrun","condrerun")) else -1

def alt_insert(kind):                     # 鼠标位置插入插件 token（与指针同定位）
    global edit_i, edit_buf
    lines = build_lines(toks)
    row = cursor_row()
    pos = len(toks)
    if row < len(lines):                     # 指针所在行的第一个 token 作为插入点
        f = min([ii for k, ii, n, p, x in row_geom(lines[row])[0]] or [len(toks)])
        pos = f
    p = make_handrun("") if kind == "handrun" else ""
    toks.insert(pos, (kind, p))
    edit_i = pos; edit_buf = ""

def space_insert():                       # 空格：插入补全匹配的 token
    global inp, edit_i
    for t, p in cands:
        if t.startswith(inp):
            wx, wy = screen_to_world(*mpos)
            i = hit(wx, wy)
            toks.insert(i if i >= 0 else len(toks), (t, ""))
            inp = ""; edit_i = -1
            return

pressed, combo = set(), set()               # 当前按下的修饰键 / 本次组合
def skey(symbol):
    if symbol in (key.LCTRL, key.RCTRL): return "ctrl"
    if symbol == key.LALT: return "altl"
    if symbol == key.RALT: return "altr"
    if symbol in (key.LSHIFT, key.RSHIFT): return "shift"
    return None

@win.event
def on_key_press(symbol, mods):
    global edit_i, edit_buf, inp
    k = skey(symbol)
    if k:                                        # 修饰键：只记录，等松开判定组合
        pressed.add(k); combo.add(k)
    elif symbol == key.SPACE:
        space_insert()
    elif edit_i >= 0 and symbol == key.ENTER: edit_i = -1
    elif edit_i >= 0 and symbol == key.BACKSPACE:
        edit_buf = edit_buf[:-1]; toks[edit_i] = (toks[edit_i][0], edit_buf)
    elif edit_i >= 0 and symbol == key.ESCAPE: edit_i = -1
    elif symbol == key.BACKSPACE: inp = inp[:-1]
    elif symbol == key.ENTER:
        for t, p in cands:
            if t.startswith(inp): inp = t; break
    elif symbol == key.ESCAPE: win.close()

@win.event
def on_key_release(symbol, mods):
    global pressed, combo, edit_i, edit_buf
    k = skey(symbol)
    if not k: return
    pressed.discard(k)
    if pressed or edit_i >= 0: return            # 还有修饰键按着 / 编辑态 → 不判定
    c = frozenset(combo)                         # 本次完整组合（全部松开时）
    combo.clear()
    if c == frozenset({"altl"}): alt_insert("read")
    elif c == frozenset({"altr"}): alt_insert("set")
    elif c == frozenset({"ctrl"}): alt_insert("cond")
    elif c in (frozenset({"ctrl","altl"}), frozenset({"ctrl","altr"})): alt_insert("handrun")
    elif c == frozenset({"ctrl","shift"}): alt_insert("condrerun")

@win.event
def on_text(text):
    global edit_buf, inp
    if edit_i >= 0:                       # 悬浮编辑 read/set/cond/handrun/condrerun payload
        if text.isalnum():
            edit_buf += text
            n, p = toks[edit_i]
            if n in ("read","set"): toks[edit_i] = (n, edit_buf)
            elif n == "cond": toks[edit_i] = (n, edit_buf)
            elif n == "condrerun": toks[edit_i] = (n, edit_buf)
            elif n == "handrun":
                _, hid = split_handrun(p)
                toks[edit_i] = (n, hid + edit_buf.encode())
    elif text == " ":                     # 空格插入 token
        space_insert()
    elif text.isalnum():
        inp += text.lower()

pyglet.app.run()
