# editor 插件：查看 editor 所在块（中键平移 + 滚轮缩放 + 块节点卡片）+ 打字实时补全
# 补全来源：零大小 data（空 key 引导块）递归收集；优先度 = 父优先度 × 父下排名 × 自身大小（越小越优）
import inspect, struct, binascii
from block import fetch
import pyglet
from pyglet.shapes import Rectangle
from pyglet.window import mouse, key
from pyglet.math import Mat4, Vec3

W, H, RW, TH, CW = 960, 640, 24, 30, 320   # 窗口/行高/标题高/卡宽
BG, CARD, HEAD, TXT = (15,18,24), (32,38,60), (40,48,70), (232,236,239)
GREEN = (98,201,130); YELLOW = (232,200,120)

# —— 定位 editor 所在块（inspect run_loop 帧的 start_key）——
key_ = b""
for f in inspect.stack()[1:]:
    if f.function == "run_loop":
        key_ = f.frame.f_locals.get("start_key", b""); break
blk = fetch(key_)

# —— 块 = token 流 → 列表 ——
def tokens(blk):
    out, i = [], 0
    while i + 4 <= len(blk):
        n = struct.unpack_from("<I", blk, i)[0]; i += 4
        if not n: break
        out.append(blk[i:i+n].decode("utf-8","replace")); i += n + 4
    return out

def crc_name(d):
    n = binascii.crc32(d if isinstance(d,bytes) else d.encode()) & 0xFFFFFFFF
    if not n: return "A"
    s = ""
    while n: s = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567"[n%32] + s; n //= 32
    return s

# —— 带超时的 fetch（server 对不存在 key 无响应，直接 fetch 会死等）——
from block import HOST, PORT
import socket
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

# —— 补全候选：零大小 data（空 key）递归收集，优先度 = 父优先度 × 排名 × 大小 ——
def collect(key=b"", prio=1.0, depth=0):
    try: toks = tokens(try_fetch(key))
    except Exception: return []
    out = []
    for i, t in enumerate(toks):
        p = prio * (i+1) * len(t)
        out.append((t, p))
        if depth < 3:
            out += collect(t.encode(), p, depth+1)
    return out

cands = sorted(collect(), key=lambda c: c[1])   # 升序：越小越优先

root = tokens(blk)
win = pyglet.window.Window(W, H, caption="SelfEdit (editor 所在块)")
cam = [0., 0., 1.]
inp = ""

# —— 渲染 ——
@win.event
def on_draw():
    import pyglet.gl as gl
    gl.glClearColor(*[c/255 for c in BG], 1); win.clear()
    win.view = Mat4.from_translation(Vec3(cam[0]+W/2, cam[1]+H/2, 0)) @ Mat4.from_scale(Vec3(cam[2], cam[2], 1))
    h = TH + len(root)*RW
    shapes = [Rectangle(0,0,CW,h,color=CARD), Rectangle(0,0,CW,TH,color=HEAD)]
    labels = [pyglet.text.Label(crc_name(key_) if key_ else "空key", x=8, y=h-TH/2,
                                font_size=12, color=GREEN+(255,), anchor_y="center")]
    for i,t in enumerate(root):
        labels.append(pyglet.text.Label(t, x=10, y=h-TH-(i+.5)*RW,
                                        font_size=11, color=TXT+(255,), anchor_y="center"))
    for s in shapes: s.draw()
    for l in labels: l.draw()
    # —— UI（屏幕坐标）：输入框 + 实时补全候选 ——
    win.view = Mat4()
    labels = [pyglet.text.Label("> " + inp, x=10, y=8, font_size=14, color=GREEN+(255,))]
    y = 30
    for t, p in cands:
        if t.startswith(inp):
            labels.append(pyglet.text.Label(f"{t}  ({p:.1f})", x=22, y=y,
                                            font_size=11, color=YELLOW+(255,), anchor_y="baseline"))
            y += 17
            if y > H-20: break
    for l in labels: l.draw()

# —— 交互：中键平移 / 滚轮缩放 / 打字补全 / Esc ——
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
def on_text(text):
    global inp
    if text.isalnum(): inp += text.lower()

@win.event
def on_key_press(symbol, mods):
    global inp
    if symbol == key.BACKSPACE: inp = inp[:-1]
    elif symbol == key.ENTER:
        for t, p in cands:
            if t.startswith(inp): inp = t; break
    elif symbol == key.ESCAPE: win.close()

pyglet.app.run()
