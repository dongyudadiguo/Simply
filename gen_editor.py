#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""gen_editor.py —— 生成 editor_blocks.h：空 key 编辑器块 + 子块（token 流）
先编译一个临时程序取 EState 各字段真实 offsetof，再拼块，保证与 editor_state.h 一致。
生成物 editor_blocks.h 由 upload_boot.c include 并上传 server。"""
import os
import struct
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.abspath(__file__))
RL = os.path.join(ROOT, "raylib-6.0_win64_mingw-w64")

FIELDS = ["camera", "mouse_world", "cur_v", "view_n", "edit_i", "tmp_ox", "tmp_oy", "tmp_ow", "tmp"]

def get_offsets():
    code = '#include "editor_state.h"\n#include <stdio.h>\n#include <stddef.h>\nint main(void){\n'
    for f in FIELDS:
        code += f'printf("{f} %zu\\n", offsetof(EState, {f}));\n'
    code += 'return 0;\n}\n'
    src = os.path.join(tempfile.gettempdir(), "estate_off.c")
    exe = os.path.join(tempfile.gettempdir(), "estate_off.exe")
    open(src, "w").write(code)
    r = subprocess.run(["gcc", "-I.", f"-I{RL}/include", src, "-o", exe], capture_output=True)
    if r.returncode != 0:
        print(r.stderr.decode("utf-8", "replace")); sys.exit(1)
    out = subprocess.run([exe], capture_output=True).stdout.decode()
    offs = {}
    for line in out.splitlines():
        k, v = line.split()
        offs[k] = int(v)
    return offs

O = get_offsets()
print("offsets:", O)

def pack4(v): return struct.pack("<I", v & 0xFFFFFFFF)

class B:
    def __init__(self, name):
        self.name = name
        self.raw = b""
    def tok(self, name, payload=b""):
        self.raw += pack4(len(name)) + name.encode() + pack4(len(payload)) + payload
        return self
    def end(self):
        self.raw += pack4(0xFFFFFFFF)
        return self

def pushi(b, v):  b.tok("push_int", f"{v}\0".encode())
def pushf(b, v):  b.tok("push_payload", struct.pack("<f", v))
def pushp(b, data): b.tok("push_payload", data)

def E(b):
    """estate 指针压栈（estate token 解引用全局变量里的指针）"""
    b.tok("estate")

def addr(b, off):
    E(b); pushi(b, off); b.tok("padd")

def ld(b, off, n):
    addr(b, off); pushi(b, n); b.tok("ld")

def st(b, off, n):
    """把栈顶 n 字节写到 estate+off（数据必须先压栈）"""
    addr(b, off); pushi(b, n); b.tok("st")

def GET(b, name): b.tok("GET", name.encode())
def SET(b, name): b.tok("SET", name.encode())
def cond(b, blk): b.tok("cond", blk.encode())
def call(b, blk): b.tok("call", blk.encode())

CAM, MW, CUV, VN, EI, OX, OY, OW, TMP = (O[f] for f in FIELDS)

def main_block():
    b = B("")
    # ---- 一次性初始化（全局变量 inited） ----
    GET(b, "inited"); b.tok("!"); cond(b, "ei")
    # ---- 每帧 ----
    call(b, "bin")                                   # 输入：字符队列 + 退格 + 补全
    call(b, "bcam")                                  # 相机：缩放/平移/mouse_world
    ld(b, MW, 8); E(b); b.tok("hit_view")            # cur_v = hit_view(mouse_world)
    st(b, CUV, 4)
    ld(b, CUV, 4); ld(b, VN, 4); b.tok(">"); cond(b, "bcv0")   # -1(0xFFFFFFFF) > view_n → 0
    E(b); b.tok("update_edit")
    E(b); b.tok("frame_combo")
    E(b); b.tok("frame_space")
    pushi(b, 256); b.tok("IsKeyPressed"); cond(b, "quit")      # ESC 退出
    E(b); b.tok("frame_focus")
    E(b); b.tok("frame_left")
    E(b); b.tok("frame_right")
    b.tok("BeginDrawing")
    pushp(b, bytes([15, 18, 24, 255])); b.tok("ClearBackground")
    ld(b, CAM, 24); b.tok("BeginMode2D")
    call(b, "bvw")                                   # 遍历视图绘制
    # ---- 指针线（token 级） ----
    E(b); b.tok("pointer_locate"); b.tok("drop")
    ld(b, OX, 8)                                     # start = (ox, oy)
    ld(b, CAM + 8, 4)                                # target.x
    b.tok("GetScreenWidth"); pushi(b, 2); b.tok("/"); b.tok("i2f")
    ld(b, CAM + 20, 4)                               # zoom
    b.tok("fdiv"); b.tok("fadd")                     # rx = target.x + (w/2)/zoom
    ld(b, OY + 4, 4)                                 # py
    pushp(b, bytes([0, 228, 48, 255])); b.tok("DrawLineV")
    b.tok("EndMode2D")
    E(b); b.tok("draw_input")
    b.tok("EndDrawing")
    E(b); b.tok("sync_views")
    E(b); b.tok("compact_views")
    b.tok("WindowShouldClose"); cond(b, "quit")
    b.tok("rerun")
    return b.end()

def blk_ei():
    b = B("ei")                                      # 一次性：窗口 + 随机种子 + inited=1
    b.tok("estate_new")
    pushf(b, 1.0); st(b, CAM + 20, 4)             # camera.zoom = 1.0（首帧前 calloc 为 0）
    pushi(b, 0); b.tok("SetTraceLogLevel")
    pushi(b, 1000); pushi(b, 700); b.tok("InitWindow")
    pushi(b, 60); b.tok("SetTargetFPS")
    b.tok("GetTickCount"); b.tok("srand")
    pushi(b, 1); SET(b, "inited")
    return b.end()

def blk_quit():
    b = B("quit")
    pushi(b, 0); b.tok("exit")
    return b.end()

def blk_bin():
    b = B("bin")
    b.tok("GetCharPressed"); SET(b, "ch")            # ch = GetCharPressed()
    GET(b, "ch"); pushi(b, 0); b.tok(">"); cond(b, "bch")
    pushi(b, 259); b.tok("IsKeyPressed"); cond(b, "bbk")   # backspace
    E(b); b.tok("update_completion")
    return b.end()

def blk_bbk():
    b = B("bbk")
    E(b); b.tok("inp_backspace")
    return b.end()

def blk_bch():
    b = B("bch")
    ld(b, EI, 4); pushi(b, 4294967295); b.tok("!="); cond(b, "bche")  # edit_i != -1
    GET(b, "ch"); E(b); b.tok("inp_append")
    call(b, "bin")
    return b.end()

def blk_bche():
    b = B("bche")
    GET(b, "ch"); E(b); b.tok("edit_append")
    call(b, "bin")
    return b.end()

def blk_bcam():
    b = B("bcam")
    b.tok("GetMouseWheelMove"); st(b, TMP, 4)        # 存 wheel
    ld(b, TMP, 4); b.tok("f2i"); pushi(b, 0); b.tok("!="); cond(b, "bwhl")
    # 共享：offset 重置 + mouse_world + 中键平移
    b.tok("GetScreenWidth"); pushi(b, 2); b.tok("/"); b.tok("i2f")
    b.tok("GetScreenHeight"); pushi(b, 2); b.tok("/"); b.tok("i2f")
    st(b, CAM, 8)
    b.tok("GetMousePosition"); ld(b, CAM, 24); b.tok("GetScreenToWorld2D")
    st(b, MW, 8)
    pushi(b, 2); b.tok("IsMouseButtonDown"); cond(b, "bpan")
    return b.end()

def blk_bwhl():
    b = B("bwhl")
    b.tok("GetMousePosition"); st(b, TMP + 8, 8)     # mpos
    ld(b, TMP + 8, 8); ld(b, CAM, 24); b.tok("GetScreenToWorld2D")
    st(b, TMP + 16, 8)                                # before
    ld(b, CAM + 20, 4)                                # zoom
    ld(b, TMP, 4)                                     # wheel
    pushf(b, 0.1); b.tok("fmul"); b.tok("fmul")       # wheel*0.1*zoom
    ld(b, CAM + 20, 4); b.tok("fadd")                 # zoom +=
    st(b, CAM + 20, 4)
    b.tok("GetScreenWidth"); pushi(b, 2); b.tok("/"); b.tok("i2f")
    b.tok("GetScreenHeight"); pushi(b, 2); b.tok("/"); b.tok("i2f")
    st(b, CAM, 8)                                     # offset = 屏幕中心
    ld(b, TMP + 16, 8)                                # before
    ld(b, TMP + 8, 8); ld(b, CAM, 24); b.tok("GetScreenToWorld2D")  # after
    b.tok("Vector2Subtract")                          # before - after
    ld(b, CAM + 8, 8); b.tok("Vector2Add")            # target +=
    st(b, CAM + 8, 8)
    return b.end()

def blk_bpan():
    b = B("bpan")
    b.tok("GetMouseDelta"); pushf(b, 1.0); ld(b, CAM + 20, 4); b.tok("fdiv")
    b.tok("Vector2Scale"); st(b, TMP + 24, 8)         # md * (1/zoom)
    ld(b, CAM + 8, 8); ld(b, TMP + 24, 8); b.tok("Vector2Subtract")
    st(b, CAM + 8, 8)                                 # target -=
    return b.end()

def blk_bvw():
    b = B("bvw")
    pushi(b, 0); SET(b, "vi")
    call(b, "bvwc")
    return b.end()

def blk_bvwc():
    b = B("bvwc")
    GET(b, "vi"); ld(b, VN, 4); b.tok("<"); cond(b, "bvwb")
    return b.end()

def blk_bvwb():
    b = B("bvwb")
    GET(b, "vi"); E(b); b.tok("draw_view")
    GET(b, "vi"); pushi(b, 1); b.tok("+"); SET(b, "vi")
    call(b, "bvwc")
    return b.end()

def blk_bcv0():
    b = B("bcv0")
    pushi(b, 0); st(b, CUV, 4)
    return b.end()

BLOCKS = {
    "": main_block().raw,
    "ei": blk_ei().raw,
    "quit": blk_quit().raw,
    "bin": blk_bin().raw,
    "bbk": blk_bbk().raw,
    "bch": blk_bch().raw,
    "bche": blk_bche().raw,
    "bcam": blk_bcam().raw,
    "bwhl": blk_bwhl().raw,
    "bpan": blk_bpan().raw,
    "bvw": blk_bvw().raw,
    "bvwc": blk_bvwc().raw,
    "bvwb": blk_bvwb().raw,
    "bcv0": blk_bcv0().raw,
}

def c_bytes(name, data):
    out = []
    for i in range(0, len(data), 12):
        chunk = data[i:i+12]
        out.append(",".join(f"0x{x:02x}" for x in chunk))
    return ",\n    ".join(out)

lines = []
lines.append("/* editor_blocks.h —— gen_editor.py 自动生成，勿手改 */")
lines.append("#ifndef EDITOR_BLOCKS_H")
lines.append("#define EDITOR_BLOCKS_H")
lines.append("#include <stdint.h>")
for key, data in BLOCKS.items():
    ident = "BLK_MAIN" if key == "" else "BLK_" + key
    lines.append(f"static const uint8_t {ident}[{len(data)}] = {{\n    {c_bytes(key, data)}\n}};")
lines.append("static const struct { const char *key; uint32_t klen; const uint8_t *data; uint32_t len; } EDITOR_BLOCKS[] = {")
for key, data in BLOCKS.items():
    ident = "BLK_MAIN" if key == "" else "BLK_" + key
    lines.append(f'    {{"{key}", {len(key.encode())}, {ident}, {len(data)}}},')
lines.append("};")
lines.append("#define EDITOR_BLOCKS_N (sizeof(EDITOR_BLOCKS)/sizeof(EDITOR_BLOCKS[0]))")
lines.append("#endif")
open(os.path.join(ROOT, "editor_blocks.h"), "w", encoding="utf-8").write("\n".join(lines) + "\n")

print("generated editor_blocks.h")
for key, data in BLOCKS.items():
    nt = data.count(b"\xff\xff\xff\xff")
    ntok = sum(1 for _ in range(0, len(data))) if False else None
    # 数 token 数
    cnt = 0; i = 0
    while i + 4 <= len(data):
        nl = struct.unpack_from("<I", data, i)[0]; i += 4
        if nl == 0xFFFFFFFF: break
        i += nl
        if i + 4 > len(data): break
        pl = struct.unpack_from("<I", data, i)[0]; i += 4 + pl
        cnt += 1
    print(f"  block {key!r}: {len(data)} bytes, {cnt} tokens")
