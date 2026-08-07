# 1553cc62ff246044c683a61e203e65541990e7fcd4af9443d22b9557ecc9ac54.py —— editor 插件（token="editor"）
# 内容：查看 editor 所在的块 —— 中键平移 + 滚轮缩放 + 节点图（块节点 + token 子节点）
# 直接代码（不加 run 层）：inspect 找 run_loop 帧 start_key = editor 所在块 key → fetch → pyglet 节点图
import inspect, struct, binascii
from block import fetch
import pyglet
from pyglet.shapes import Rectangle
from pyglet.window import mouse, key
from pyglet.math import Mat4, Vec3

# ---- 1. 找 editor 所在的块（调用栈中 run_loop 帧的 start_key）----
blk_key = b""
for frame in inspect.stack()[1:]:
    if frame.function == "run_loop":
        blk_key = frame.frame.f_locals.get("start_key", b"")
        break
block_data = fetch(blk_key)                     # 取 editor 所在块的二进制

# ---- 2. 块 = token 流，解析成列表 ----
def parse_tokens(blk):
    toks, i = [], 0
    while i + 4 <= len(blk):
        n = struct.unpack_from("<I", blk, i)[0]; i += 4
        if n == 0: break
        toks.append(blk[i:i + n].decode("utf-8", "replace")); i += n
        if i + 4 > len(blk): break               # 容错：无尾部 extra 4B
        i += 4                                    # 跳过每条后的 4 字节（extra/dlen）
    return toks

def crc_name(data):
    if isinstance(data, str): data = data.encode()
    n = binascii.crc32(data) & 0xFFFFFFFF
    if n == 0: return "A"
    ch = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567"
    out = []
    while n: out.append(ch[n % 32]); n //= 32
    return "".join(reversed(out))

root_tokens = parse_tokens(block_data)

# ---- 3. pyglet 节点图：中键平移 + 滚轮缩放 ----
W, H = 960, 640
ROW_H, TITLE_H, CARD_W = 24, 30, 320
BG = (15, 18, 24)
CARD_BG = (32, 38, 60); HEAD = (40, 48, 70)
TEXT_C = (232, 236, 239); DIM = (102, 113, 125)
GREEN = (98, 201, 130); EDGE = (52, 65, 77)

win = pyglet.window.Window(W, H, caption="SelfEdit (editor 所在块)")
cam = [0.0, 0.0, 1.0]                            # 平移 x/y + 缩放
def screen_to_world(x, y):
    s = cam[2]
    return ((x - W/2 - cam[0]) / s, (y - H/2 - cam[1]) / s)

@win.event
def on_draw():
    import pyglet.gl as gl
    gl.glClearColor(BG[0]/255, BG[1]/255, BG[2]/255, 1)
    win.clear()
    s = cam[2]
    win.view = Mat4.from_translation(Vec3(cam[0] + W/2, cam[1] + H/2, 0)) @ Mat4.from_scale(Vec3(s, s, 1))
    texts = []; shapes = []
    def card(x, y, title, toks, tcolor):
        h = TITLE_H + len(toks) * ROW_H
        shapes.append(Rectangle(x, y, CARD_W, h, color=CARD_BG))
        shapes.append(Rectangle(x, y, CARD_W, TITLE_H, color=HEAD))
        texts.append(pyglet.text.Label(title, x=x+8, y=y+h-TITLE_H/2,
                     font_size=12, color=tcolor+(255,), anchor_y="center"))
        for i, t in enumerate(toks):
            texts.append(pyglet.text.Label(t, x=x+10, y=y+h-TITLE_H-(i+0.5)*ROW_H,
                         font_size=11, color=TEXT_C+(255,), anchor_y="center"))
        return h
    # 根块节点（editor 所在块）
    title = crc_name(blk_key) if blk_key else "空key(引导块)"
    ch = card(0.0, 0.0, title, root_tokens, GREEN)
    for s in shapes: s.draw()
    for t in texts: t.draw()

@win.event
def on_mouse_drag(x, y, dx, dy, bt, mods):
    if bt & mouse.MIDDLE:                       # 中键平移
        cam[0] += dx; cam[1] += dy

@win.event
def on_mouse_scroll(x, y, sx, sy):
    k = 1.1 if sy > 0 else 0.9                  # 滚轮缩放（以鼠标位置为锚点）
    s = cam[2]
    wx = (x - W/2 - cam[0]) / s                 # 鼠标处的世界坐标
    wy = (y - H/2 - cam[1]) / s
    ns = max(0.05, min(20, s * k))
    cam[0] = x - W/2 - wx * ns                  # 保持鼠标处世界点不动
    cam[1] = y - H/2 - wy * ns
    cam[2] = ns


@win.event
def on_key_press(symbol, mods):
    if symbol == key.ESCAPE:
        win.close()

pyglet.clock.schedule_interval(lambda dt: None, 1/60)
pyglet.app.run()
