# editor 插件：查看/编辑 editor 所在块的 token 流（纵向行布局）
# 普通 token 独占一行；read 变量贴指令左侧、set 变量贴右侧（a b add c）；有值只显 payload
# 左 Alt 插 read、右 Alt 插 set、悬浮 read/set 编辑 payload；中键平移+滚轮缩放+补全
import inspect, struct, binascii
from block import fetch, HOST, PORT
import socket, pyglet
from pyglet.shapes import Rectangle
from pyglet.window import mouse, key
from pyglet.math import Mat4, Vec3

W, H, RH, GAP = 960, 640, 30, 8          # 窗口/行高/行距
BG, CARD, TXT = (15,18,24), (32,38,60), (232,236,239)
GREEN, YELLOW, BLUE = (98,201,130), (232,200,120), (127,184,216)

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

# —— 补全候选：零大小 data（空 key）递归收集，优先度 = 父优先度 × 排名 × 大小 ——
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

toks = tokens(fetch(key_))                # [(name, payload), ...] 本地可编辑
win = pyglet.window.Window(W, H, caption="SelfEdit (editor 所在块)")
cam = [0., 0., 1.]
inp, edit_i, edit_buf = "", -1, ""

def label(n, p): return p if n in ("read","set") and p else (n or "?")
def item_w(n, p): return len(label(n,p))*9 + 20

def row_geom(line):                       # 行内各项 [(kind, i, n, p, x)]，x 为世界坐标
    items, x = [], 0.0
    for it in line["left"]:
        i, n, p = it; items.append(("l", i, n, p, x)); x += item_w(n,p) + 6
    if line["name"]:
        i, n, p = line["name"]; items.append(("n", i, n, p, x)); x += item_w(n,p) + 6
    for it in line["right"]:
        i, n, p = it; items.append(("r", i, n, p, x)); x += item_w(n,p) + 6
    return items, x

def hit(wx, wy):                          # 世界坐标 → toks 索引（-1 无）
    row = int(-wy / (RH+GAP))
    lines = build_lines(toks)
    if not (0 <= row < len(lines)): return -1
    items, _ = row_geom(lines[row])
    for kind, i, n, p, x in items:
        if x <= wx <= x + item_w(n,p): return i
    return -1

def screen_to_world(x, y):
    s = cam[2]
    return ((x - W/2 - cam[0]) / s, (y - H/2 - cam[1]) / s)

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
            lb = label(n,p); w = item_w(n,p)
            if kind == "n":
                bg, col = CARD, TXT
            elif kind == "l":
                bg, col = GREEN, (255,255,255)
            else:
                bg, col = YELLOW, (255,255,255)
            shapes.append(Rectangle(x, y, w, RH, color=BLUE if i == edit_i else bg))
            labels.append(pyglet.text.Label(lb, x=x+10, y=y+RH/2, font_size=13,
                                            color=col+(255,), anchor_y="center"))
    for s in shapes: s.draw()
    for l in labels: l.draw()
    # —— UI（屏幕坐标）——
    win.view = Mat4()
    labels = [pyglet.text.Label("> " + inp, x=10, y=8, font_size=14, color=GREEN+(255,))]
    y = 30
    for t, p in cands:
        if t.startswith(inp):
            labels.append(pyglet.text.Label(f"{t}  ({p:.1f})", x=22, y=y, font_size=11, color=YELLOW+(255,)))
            y += 17
            if y > H-20: break
    for l in labels: l.draw()

# —— 交互 ——
@win.event
def on_mouse_drag(x, y, dx, dy, bt, mods):
    if bt & mouse.MIDDLE: cam[0]+=dx; cam[1]+=dy

@win.event
def on_mouse_scroll(x, y, sx, sy):
    k = 1.1 if sy>0 else .9; s = cam[2]
    wx, wy = (x-W/2-cam[0])/s, (y-H/2-cam[1])/s
    ns = max(.05, min(20, s*k))
    cam[0], cam[1], cam[2] = x-W/2-wx*ns, y-H/2-wy*ns, ns

@win.event
def on_mouse_motion(x, y, dx, dy):
    global edit_i
    wx, wy = screen_to_world(x, y)
    i = hit(wx, wy)
    edit_i = i if (i >= 0 and toks[i][0] in ("read","set")) else -1

def alt_insert(kind):                     # 鼠标位置插入 read/set
    global edit_i, edit_buf
    wx, wy = screen_to_world(*win.get_pointer_position())
    i = hit(wx, wy)
    toks.insert(i if i >= 0 else len(toks), (kind, ""))
    edit_i = i if i >= 0 else len(toks)-1; edit_buf = ""

@win.event
def on_key_press(symbol, mods):
    global edit_i, edit_buf, inp
    if symbol == key.LALT: alt_insert("read")
    elif symbol == key.RALT: alt_insert("set")
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
def on_text(text):
    global edit_buf, inp
    if edit_i >= 0:
        if text.isalnum():
            edit_buf += text; toks[edit_i] = (toks[edit_i][0], edit_buf)
    elif text.isalnum():
        inp += text.lower()

pyglet.app.run()
