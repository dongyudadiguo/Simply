# _pyglet_proto.py —— pyglet 高上限节点图原型（巅峰卡片 + 批量渲染 + GPU 相机）
# 运行: python _pyglet_proto.py  （真机弹窗；滚轮缩放，右键/中键拖拽平移）
import pyglet
from pyglet.graphics import Batch
from pyglet.shapes import Rectangle, Line
from pyglet.window import mouse
from pyglet.math import Mat4, Vec3

W, H = 1280, 800
ROW_H, TITLE_H, CARD_W = 24, 30, 340
BG = (15, 18, 24)
CATS = [(200,224,160),(232,200,120),(127,184,216),(94,200,232),(208,128,224),(224,160,80),(247,118,142)]
GREEN = (98,201,130)

N_CARDS = 400          # 真机可调到 5000 看上限
TOKENS = 10

batch = Batch()
for ci in range(N_CARDS):
    x = (ci % 25) * (CARD_W + 50)
    y = (ci // 25) * (TITLE_H + TOKENS*ROW_H + 90)
    h = TITLE_H + TOKENS*ROW_H + 8
    Rectangle(x, y, CARD_W, h, color=(32,38,60), batch=batch)
    Rectangle(x, y, CARD_W, TITLE_H, color=(40,48,70), batch=batch)
    Line(x, y+TITLE_H, x+CARD_W, y+TITLE_H, thickness=1, color=(52,65,77), batch=batch)
    for r in range(TOKENS):
        y0 = y + TITLE_H + r*ROW_H
        cat = CATS[(ci*3+r) % len(CATS)]
        Rectangle(x+8, y0+5, 12, 14, color=cat, batch=batch)
        Rectangle(x+24, y0+8, 30+((ci+r)%4)*12, 8, color=(90,100,120), batch=batch)
        Line(x+4, y0+ROW_H, x+CARD_W-4, y0+ROW_H, thickness=1, color=(26,32,44), batch=batch)
    if ci < N_CARDS-1:
        Line(x+CARD_W, y+h//2, x+CARD_W+50, y+h//2, thickness=2, color=GREEN, batch=batch)

win = pyglet.window.Window(W, H, "pyglet 高上限原型 %d 卡" % N_CARDS)
cam = [0.0, 0.0, 1.0]
fps = pyglet.window.FPSDisplay(win)

@win.event
def on_draw():
    win.clear()
    s = cam[2]
    win.view = Mat4.from_translation(Vec3(cam[0], cam[1], 0)) @ Mat4.from_scale(Vec3(s, s, 1))
    batch.draw()
    fps.draw()

@win.event
def on_mouse_drag(x, y, dx, dy, bt, mods):
    if bt & (mouse.MIDDLE | mouse.RIGHT):
        cam[0] += dx; cam[1] += dy

@win.event
def on_mouse_scroll(x, y, sx, sy):
    cam[2] *= 1.1 if sy > 0 else 0.9
    cam[2] = max(0.05, min(20, cam[2]))

pyglet.app.run()
