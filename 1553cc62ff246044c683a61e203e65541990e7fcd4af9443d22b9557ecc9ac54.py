# editor 插件：查看 editor 所在块（中键平移 + 滚轮缩放 + 块节点卡片）
import inspect, struct, binascii
from block import fetch
import pyglet
from pyglet.shapes import Rectangle
from pyglet.window import mouse, key
from pyglet.math import Mat4, Vec3

W, H, RW, TH, CW = 960, 640, 24, 30, 320   # 窗口/行高/标题高/卡宽
BG, CARD, HEAD, TXT = (15,18,24), (32,38,60), (40,48,70), (232,236,239)
GREEN = (98,201,130)

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
        out.append(blk[i:i+n].decode("utf-8","replace")); i += n + 4  # 跳过每条后 extra 4B
    return out

def crc_name(d):
    n = binascii.crc32(d if isinstance(d,bytes) else d.encode()) & 0xFFFFFFFF
    if not n: return "A"
    s = ""
    while n: s = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567"[n%32] + s; n //= 32
    return s

root = tokens(blk)
win = pyglet.window.Window(W, H, caption="SelfEdit (editor 所在块)")
cam = [0., 0., 1.]                            # 平移 + 缩放

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

# —— 交互：中键平移 / 滚轮以鼠标为锚缩放 / Esc 关闭 ——
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
def on_key_press(symbol, mods):
    if symbol == key.ESCAPE: win.close()

pyglet.app.run()
