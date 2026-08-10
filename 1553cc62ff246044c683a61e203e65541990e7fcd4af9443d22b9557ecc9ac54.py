# editor 插件：token 流编辑器（纵向行布局）
# 空格=插入补全token | Ctrl=cond Ctrl+Alt=handrun Shift+Ctrl=condrerun | 右键拖出重排
# read/set 贴指令左右；命中/未命中颜色；cond/handrun/condrerun 热力高亮+悬浮编辑+handrun按钮
# 中键平移+滚轮缩放；补全跟随鼠标（零大小data，优先度=父优先度×排名×大小）
import inspect, struct, binascii, hashlib, os, importlib
from block import fetch, recv_all, run_block, HOST, PORT, HERE
import socket, pyglet, ctypes, vmstate, time
from pyglet.shapes import Circle, Line
from pyglet.window import mouse, key
from pyglet.math import Mat4, Vec3

W, H, RH, GAP = 960, 640, 30, 8          # 窗口/行高/行距
BG, CARD, DIM, TXT = (15,18,24), (32,38,60), (70,80,90), (232,236,239)
GREEN, YELLOW, BLUE = (98,201,130), (232,200,120), (127,184,216)
COND, HAND, CRUN = (208,128,224), (247,118,142), (255,158,100)   # cond/handrun/condrerun 基色
HOT, HIT = (255,80,80), (90,160,220)     # 热力/命中

# —— 定位 editor 所在块 ——
if not hasattr(vmstate, "ed_init"):
    key_ = b""
    for f in inspect.stack()[1:]:
        if f.function == "run_block":
            key_ = f.frame.f_locals.get("start_key", b""); break

    # —— 块 = [(name, payload)] ——
    def tokens(blk):
        out, i = [], 0
        while i + 4 <= len(blk):
            n = struct.unpack_from("<I", blk, i)[0]; i += 4
            if not n: break
            name = blk[i:i+n].decode("utf-8","replace"); i += n
            d = struct.unpack_from("<I", blk, i)[0]; i += 4
            p = blk[i:i+d]
            out.append((name, p if name == "handrun" else p.decode("utf-8","replace"))); i += d
        return out

    def plugin_exists(name):
        return os.path.exists(os.path.join(HERE, hashlib.sha256(name.encode()).hexdigest()+".py"))

    def encode_toks(ts):                     # 块序列化（tokens 的逆）→ upload 用
        out = b""
        for n, p in ts:
            b = n.encode()
            out += struct.pack("<I", len(b)) + b
            pb = p if isinstance(p, bytes) else p.encode()
            out += struct.pack("<I", len(pb)) + pb
        return out + struct.pack("<I", 0)

    def exec_plugin(token):                  # 运行按钮：沿引用链下钻执行目标块
        if not token: return
        try:
            run_block(token.encode())         # 下钻：目标块开头 token 命中插件则执行，否则继续
        except Exception:
            pass

    def cur_toks():                          # 当前编辑视图的 token 流
        return toks if edit_v < 0 else subviews[edit_v]["toks"]

    def hit_view(sv, wx, wy):                # 子视图内命中 → 项索引（节点头顶=pos.y+RH）
        bx, by = sv["pos"]
        dist = (by + RH) - wy
        row = int((max(0, dist) + GAP) // (RH+GAP)) - 1   # 节点头占一行
        lines = build_lines(sv["toks"])
        if not (0 <= row < len(lines)): return -1
        for kind, i, n, p, x in row_geom(lines[row])[0]:
            if bx + x <= wx <= bx + x + item_w(n,p): return i
        return -1

    def find_item_v(v, i):                   # 视图内项位置 → (world x, world y, name, payload)
        if v < 0: ts, ox, oy = toks, 0.0, 0.0
        else: ts, ox, oy = subviews[v]["toks"], subviews[v]["pos"][0], subviews[v]["pos"][1]
        for r, line in enumerate(build_lines(ts)):
            for k, ii, n, p, x in row_geom(line)[0]:
                if ii == i: return ox + x, row_y(oy, r), n, p
        return None

    def insert_point(ts, ox, oy):            # 鼠标在视图(原点 ox,oy=节点头行)内 → 插入位置
        wx, wy = screen_to_world(*mpos)
        dist = (oy + RH) - wy
        row = int((max(0, dist) + GAP) // (RH+GAP)) - 1   # 节点头占一行
        lines = build_lines(ts)
        if 0 <= row < len(lines):
            f = min([ii for k, ii, n, p, x in row_geom(lines[row])[0]] or [len(ts)])
            return f
        return len(ts)

    # —— handrun payload: 8字节id + 目标token；布尔由 id 索引 ——

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

    def row_y(oy, row):                  # 视图内容行 row 中心 y（world）；视图原点=节点头行
        return oy - (row+1)*(RH+GAP) + RH/2

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

    def upload(key, data):                       # op=3：上传数据（响应 4B idx）
        with socket.create_connection((HOST, PORT), timeout=3) as s:
            s.sendall(b"\x03" + struct.pack("<I", len(key)) + key +
                      struct.pack("<I", len(data)) + data)
            return struct.unpack("<I", recv_all(s, 4))[0]

    def collect(key=b"", prio=1.0, depth=0):
        try: ts = tokens(try_fetch(key))
        except Exception: return []
        out = []
        for i, (t, _) in enumerate(ts):
            p = prio * (i+1) * len(t)
            out.append((t, p))
            if depth < 3: out += collect(t.encode(), p, depth+1)
        return out

    # 补全候选 = 递归块引用（collect）+ 本地插件指令名（add/read/set/cond/handrun/condrerun 等）
    PLUGIN_NAMES = ["boot","editor","rerun","add","read","set","cond","handrun","condrerun",
                   "push_int","in-int","out","rand","gt","lt","eq","mul","ret_int"]
    cands = sorted(collect() + [(t, 100.0) for t in PLUGIN_NAMES], key=lambda c: c[1])
    toks = tokens(fetch(key_))                # 本地可编辑 [(name, payload)]
    vmstate.cur[key_] = toks                 # 挂共享：run_block 运行前对比哈希用
    win = pyglet.window.Window(W, H, caption="SelfEdit (editor 所在块)")
    @win.event
    def on_close():
        vmstate.ed_open = False   # 窗口关闭 → 停止帧渲染/接棒（链结束）
        win.close()

    cam = [0., 0., 1.]
    inp, edit_i, edit_buf, edit_v = "", -1, "", -1
    mpos = (W/2, H/2)
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
        lines = build_lines(toks)
        dist = RH - wy                             # 节点头顶(y=RH)向下
        row = int((max(0, dist) + GAP) // (RH+GAP)) - 1   # 节点头占一行 → 内容行减1
        if not (0 <= row < len(lines)): return -1
        for kind, i, n, p, x in row_geom(lines[row])[0]:
            if x <= wx <= x + item_w(n,p): return i
        return -1

    def screen_to_world(x, y):
        s = cam[2]
        return ((x - W/2 - cam[0]) / s, (y - H/2 - cam[1]) / s)

    def gaps():                                     # 所有行间隙位置（世界 y）
        n = len(build_lines(toks))
        gs = [11.0]                             # 节点头与行0 之间
        for i in range(1, n):
            gs.append(-(RH+GAP)*i - GAP/2)      # 行 i-1 与 行 i 之间
        gs.append(-(RH+GAP)*(n-1) - RH - (RH+GAP)/2)    # 末尾下方
        return gs

    def cursor_row():                              # 吸附到离鼠标最近的间隙
        wx, wy = screen_to_world(*mpos)
        gs = gaps()
        return min(range(len(gs)), key=lambda i: abs(gs[i] - wy))

    def subview_gaps(sv):                         # 子视图间隙（世界 y，节点头后）
        by = sv["pos"][1]
        n = len(build_lines(sv["toks"]))
        gs = [by + 11.0]                        # 节点头与行0 之间
        for i in range(1, n):
            gs.append(by - (RH+GAP)*i - GAP/2)
        gs.append(by - (RH+GAP)*(n-1) - RH - (RH+GAP)/2)
        return gs

    def pointer_y():                              # 指针 = 鼠标所在视图的最近间隙
        wx, wy = screen_to_world(*mpos)
        si = hit_subview(wx, wy)
        gs = subview_gaps(subviews[si]) if si >= 0 else gaps()
        return gs[min(range(len(gs)), key=lambda i: abs(gs[i] - wy))]

    # —— 渲染 ——
    @win.event
    def on_draw():
        import pyglet.gl as gl
        gl.glClearColor(*[c/255 for c in BG], 1); win.clear()
        win.view = Mat4.from_translation(Vec3(cam[0]+W/2, cam[1]+H/2, 0)) @ Mat4.from_scale(Vec3(cam[2], cam[2], 1))
        shapes, labels = [], []
        anchors.clear()
        # 节点头：初始节点显示块名（对齐拖出节点的节点头）
        labels.append(pyglet.text.Label(crc_name(key_), x=2, y=RH/2, font_size=13,
                                        color=(120,130,145)+(255,), anchor_y="center"))
        for row, line in enumerate(build_lines(toks)):
            y = row_y(0.0, row)
            for kind, i, n, p, x in row_geom(line)[0]:
                anchors[(-1, i)] = (x+2, y)            # 记录锚点（对齐 transition func_pos）
                lb = label(n, p)
                col = item_color(n)                    # 纯文字颜色（无矩形背景）
                if n in ("cond","handrun","condrerun") and heat.get(n):   # 热力：文字偏 HOT
                    col = tuple(int(col[j] + (HOT[j]-col[j])*min(heat.get(n,0)*.2,1)) for j in range(3))
                if i == edit_i and edit_v < 0: col = (255,255,255)    # 悬浮编辑项白字
                labels.append(pyglet.text.Label(lb, x=x+2, y=y, font_size=13,
                                                color=col+(255,), anchor_y="center"))
                if n == "handrun":                     # handrun 两个按钮（小圆点）
                    _, hid = split_handrun(p)
                    f = vmstate.hand_flags.get(hid, [0, 0])
                    for bi in (0, 1):
                        bx = x + item_w(n,p) - 26 + bi*12
                        shapes.append(Circle(bx, y, 3, color=(255,200,80) if f[bi] else (70,80,90)))
        # 指针：鼠标所在视图的插入行水平线（从视图起点到鼠标，对齐 transition）
        wx, wy = screen_to_world(*mpos)
        si = hit_subview(wx, wy)
        sx0 = subviews[si]["pos"][0] if si >= 0 else 0.0
        py = pointer_y()
        shapes.append(Line(sx0, py, max(wx, sx0+20), py, thickness=2, color=(150,160,170)))
        # —— 拖出的子视图：显示其 token 行 + 父-子连线（对齐 transition：纯文字、锚点连线）——
        for si, sv in enumerate(subviews):
            bx, by = sv["pos"]
            rows = build_lines(sv["toks"])
            # 节点头：块名（空块也显示节点头，可点击插入）
            nm = sv["bkey"].decode("utf-8","replace") if isinstance(sv["bkey"], bytes) else str(sv["bkey"])
            col = item_color(nm)
            if edit_v == si and (not rows or edit_i < 0): col = (255,255,255)   # 悬停节点头 → 白字
            labels.append(pyglet.text.Label(nm or "(空)", x=bx+2, y=by+RH/2, font_size=13,
                                            color=col+(255,), anchor_y="center"))
            for row, line in enumerate(rows):
                yy = row_y(by, row)
                for kind, ii, nn, pp, xx in row_geom(line)[0]:
                    anchors[(si, ii)] = (bx+xx+2, yy)    # 子视图 token 锚点（支持嵌套拖出）
                    lb = label(nn, pp)
                    col = item_color(nn)
                    if ii == edit_i and edit_v == si: col = (255,255,255)   # 子视图编辑态白字
                    labels.append(pyglet.text.Label(lb, x=bx+xx+2, y=yy, font_size=13,
                                                    color=col+(255,), anchor_y="center"))
                    if nn == "handrun":                  # 子视图 handrun 按钮
                        _, hid = split_handrun(pp)
                        f = vmstate.hand_flags.get(hid, [0, 0])
                        for bi in (0, 1):
                            bx2 = bx + xx + item_w(nn,pp) - 26 + bi*12
                            shapes.append(Circle(bx2, yy, 3, color=(255,200,80) if f[bi] else (70,80,90)))
        # 父-子连线：从源 token 锚点 → 子视图左上（对齐 transition func_pos → views_pos）
        for si, sv in enumerate(subviews):
            a = anchors.get(sv["src"])
            if a:
                shapes.append(Line(a[0], a[1], sv["pos"][0], sv["pos"][1], thickness=1, color=(98,201,130)))
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
        global cam, drag_sv
        if bt & mouse.MIDDLE: cam[0]+=dx; cam[1]+=dy
        elif drag_sv >= 0 and (bt & mouse.LEFT or bt & mouse.RIGHT):   # 右键拖出 / 左键拖动 相对位移跟随（对齐 transition 增量）
            s = cam[2]
            p = subviews[drag_sv]["pos"]
            subviews[drag_sv]["pos"] = (p[0] + dx/s, p[1] + dy/s)

    @win.event
    def on_mouse_scroll(x, y, sx, sy):
        k = 1.1 if sy>0 else .9; s = cam[2]
        wx, wy = (x-W/2-cam[0])/s, (y-H/2-cam[1])/s
        ns = max(.05, min(20, s*k))
        cam[0], cam[1], cam[2] = x-W/2-wx*ns, y-H/2-wy*ns, ns

    def find_item(i):                          # toks 索引 → (行y, 项x, name, payload)
        for row, line in enumerate(build_lines(toks)):
            y = row_y(0.0, row)
            for kind, ii, n, p, x in row_geom(line)[0]:
                if ii == i: return y, x, n, p
        return None

    subviews = []                            # 右键拖出的独立子视图 [{"key","bkey","toks","pos","src"}] src=(view,token_idx)
    drag_sv = -1                              # 正在拖动的子视图索引
    anchors = {}                              # (view_idx, token_idx) -> (world x, world y) 渲染时记录每个 token 锚点（对齐 transition func_pos）

    def hit_subview(wx, wy):                  # 命中子视图 → 索引（-1 无；含空块，对齐节点头布局）
        for si, sv in enumerate(subviews):
            n = len(build_lines(sv["toks"]))
            by = sv["pos"][1]
            top = by + RH                    # 节点头顶
            bot = by - n*(RH+GAP)            # 内容行 n-1 底（n=0 → by，仅节点头行）
            if top >= wy >= bot and wx >= sv["pos"][0]-20:
                return si
        return -1

    @win.event
    def on_mouse_press(x, y, button, mods):
        global drag_sv, edit_i
        wx, wy = screen_to_world(x, y)
        if button == mouse.RIGHT:
            edit_i = -1
            si = hit_subview(wx, wy)
            if si >= 0:                            # 右键点击子视图 → 关闭节点
                del subviews[si]
                drag_sv = -1
                return
            i = hit(wx, wy)                        # 主视图 token → 右键拖出（不变）
            if i >= 0:
                n, pp = toks[i]
                if n == "handrun":                 # handrun → 拖出 payload 里的目标 token
                    target, _ = split_handrun(pp)
                    if not target: return          # 无目标 → 不拖出
                    key = target.encode()
                else:                              # 普通 token → 自身名即块 key
                    key = n.encode()
                try:                               # 目标块存在 → 拖出子块为独立视图
                    sub = tokens(try_fetch(key))
                except Exception:                  # 服务器无 → 上传 4 字节全零占位
                    upload(key, b"\x00\x00\x00\x00")
                    sub = tokens(try_fetch(key))   # 重新取（现在存在）
                subviews.append({"key": n, "bkey": key, "toks": sub, "pos": (wx, wy), "src": (-1, i)})
                vmstate.cur[key] = sub             # 挂共享（子视图内容）
                drag_sv = len(subviews)-1          # 新子视图跟随鼠标
        elif button == mouse.LEFT:
            si = hit_subview(wx, wy)
            if si >= 0:                            # 点的是子视图
                v, ts = si, subviews[si]["toks"]
                i = hit_view(subviews[si], wx, wy)
                if i < 0:                          # 子视图空白 → 左键拖动节点
                    drag_sv = si
                    return
            else:                                  # 主视图
                v, ts = -1, toks
                i = hit(wx, wy)
            if i >= 0 and ts[i][0] == "handrun":   # 点 handrun 两个按钮（项右端 24px）
                _, hid = split_handrun(ts[i][1])
                fl = vmstate.hand_flags.setdefault(hid, [0, 0])
                gi = find_item_v(v, i)
                rel = wx - (gi[0] + item_w(gi[2],gi[3]) - 24)
                hitb = 0 if 0 <= rel < 12 else (1 if 12 <= rel < 24 else -1)
                if hitb >= 0:                      # 命中按钮 → 只改 id 指向的 flags（不执行）
                    fl[hitb] = 1 - fl[hitb]
                    vmstate.hand_flags[hid] = fl
            else:
                edit_i = -1

    @win.event
    def on_mouse_release(x, y, button, mods):
        global drag_sv
        if button in (mouse.RIGHT, mouse.LEFT): drag_sv = -1

    @win.event
    def on_mouse_motion(x, y, dx, dy):
        global edit_i, edit_v, mpos
        try:                                   # 鼠标进窗口 → 自动获得键盘焦点（否则收不到按键）
            if ctypes.windll.user32.GetFocus() != win._hwnd:
                ctypes.windll.user32.SetFocus(win._hwnd)
        except Exception:
            pass
        mpos = (x, y)
        wx, wy = screen_to_world(x, y)
        si = hit_subview(wx, wy)
        if si >= 0:                              # 鼠标在子视图 → 编辑子视图
            edit_v = si
            i = hit_view(subviews[si], wx, wy)
        else:                                    # 主视图
            edit_v = -1
            i = hit(wx, wy)
        edit_i = i if (i >= 0 and cur_toks()[i][0] in ("read","set","cond","handrun","condrerun")) else -1

    def alt_insert(kind):                     # 鼠标位置插入插件 token（当前视图）
        global edit_i, edit_buf, edit_v
        ts = cur_toks()
        if edit_v < 0: ox, oy = 0.0, 0.0
        else: ox, oy = subviews[edit_v]["pos"][0], subviews[edit_v]["pos"][1]
        pos = insert_point(ts, ox, oy)
        p = make_handrun("") if kind == "handrun" else ""
        ts.insert(pos, (kind, p))
        edit_i = pos; edit_buf = ""

    def space_insert():                       # 空格：插入补全匹配的 token；无匹配也直接插入输入的文本（当前视图）
        global inp, edit_i, edit_v
        ts = cur_toks()
        if edit_v < 0: ox, oy = 0.0, 0.0
        else: ox, oy = subviews[edit_v]["pos"][0], subviews[edit_v]["pos"][1]
        pos = insert_point(ts, ox, oy)
        t = inp                                  # 默认：直接插入输入文本作为 token 名
        for name, p in cands:
            if name.startswith(inp):             # 有补全匹配 → 用补全名
                t = name
                break
        ts.insert(pos, (t, ""))
        inp = ""; edit_i = -1

    copy_buf = []                                 # 复制缓冲区（SHIFT 划选段）
    sel_start = -1                                # SHIFT 划选起点（对齐 transition copy2[0]）
    del_start = -1                                # DELETE 划选起点（对齐 transition copy=point）

    def cur_pos():                                # 鼠标在所在视图的插入位置（token 索引）
        ts = cur_toks()
        if edit_v < 0: ox, oy = 0.0, 0.0
        else: ox, oy = subviews[edit_v]["pos"][0], subviews[edit_v]["pos"][1]
        return insert_point(ts, ox, oy)

    pressed, combo = set(), set()               # 当前按下的修饰键 / 本次组合
    def skey(symbol):
        if symbol in (key.LCTRL, key.RCTRL): return "ctrl"
        if symbol == key.LALT: return "altl"
        if symbol == key.RALT: return "altr"
        if symbol in (key.LSHIFT, key.RSHIFT): return "shift"
        return None

    @win.event
    def on_key_press(symbol, mods):
        global edit_i, edit_buf, inp, sel_start, del_start
        k = skey(symbol)
        if k:                                        # 修饰键：只记录，等松开判定组合
            if k == "shift" and edit_i < 0 and not (mods & (key.MOD_CTRL | key.MOD_ALT)):
                sel_start = cur_pos()                # SHIFT 划选起点（对齐 transition copy2[0]）
            pressed.add(k); combo.add(k)
        elif symbol == key.DELETE and edit_i < 0:
            del_start = cur_pos()                    # DELETE 划选起点（对齐 transition copy=point）
        elif symbol == key.INSERT and edit_i < 0 and copy_buf:
            ts = cur_toks()                          # INSERT 粘贴（对齐 transition memcpy+memmove）
            pos = cur_pos()
            for i, tok in enumerate(copy_buf):
                ts.insert(pos + i, tok)
        elif symbol == key.SPACE:
            space_insert()
        elif edit_i >= 0 and symbol == key.ENTER: edit_i = -1
        elif edit_i >= 0 and symbol == key.BACKSPACE:
            edit_buf = edit_buf[:-1]
            ts = cur_toks(); ts[edit_i] = (ts[edit_i][0], edit_buf)
        elif edit_i >= 0 and symbol == key.ESCAPE: edit_i = -1
        elif symbol == key.BACKSPACE: inp = inp[:-1]
        elif symbol == key.ENTER:
            for t, p in cands:
                if t.startswith(inp): inp = t; break
        elif symbol == key.ESCAPE: win.close()

    @win.event
    def on_key_release(symbol, mods):
        global pressed, combo, edit_i, edit_buf, sel_start, del_start
        if symbol == key.DELETE and del_start >= 0:
            ts = cur_toks()                          # DELETE 松开 → 删除划选段（对齐 transition memmove）
            pos = cur_pos()
            a, b = min(del_start, pos), max(del_start, pos)
            del ts[a:b]
            del_start = -1
            return
        k = skey(symbol)
        if not k: return
        if k == "shift" and sel_start >= 0 and not (mods & (key.MOD_CTRL | key.MOD_ALT)):
            ts = cur_toks()                          # SHIFT 松开 → 记录复制段（对齐 transition copy2[1]）
            pos = cur_pos()
            a, b = min(sel_start, pos), max(sel_start, pos)
            copy_buf = list(ts[a:b])
            sel_start = -1
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
        global edit_buf, inp, edit_v
        if edit_i >= 0:                       # 悬浮编辑 read/set/cond/handrun/condrerun payload
            if text.isalnum():
                edit_buf += text
                ts = cur_toks(); n, p = ts[edit_i]
                if n in ("read","set"): ts[edit_i] = (n, edit_buf)
                elif n == "cond": ts[edit_i] = (n, edit_buf)
                elif n == "condrerun": ts[edit_i] = (n, edit_buf)
                elif n == "handrun":
                    _, hid = split_handrun(p)
                    ts[edit_i] = (n, hid + edit_buf.encode())

        elif text.isalnum():
            inp += text.lower()

    vmstate.ed_win = win
    vmstate.ed_open = True
    vmstate.ed_init = True
    while vmstate.ed_open:          # devdest 渲染主循环：窗口常驻，每帧处理输入+重绘
        win.dispatch_events()
        if not vmstate.ed_open: break   # dispatch 中可能触发 on_close 关窗 → 立即退出
        win.dispatch_event('on_draw')
        win.flip()
        time.sleep(0.016)
    run_next()                      # 窗口关闭 → 接棒（rerun 重跑触发 flush 保存后链结束）

else:
    pass                            # 重跑：已初始化，不渲染不接棒（不递归、不堆积）
