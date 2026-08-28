#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Simply 一体化构建脚本（替代原 build.bat / build_fn.bat）。

在项目根目录运行：
    python build.py

产物：
    server.exe / upload_boot.exe / block.dll / vm.exe / raylib.dll
    全部插件 <sha256(token)>.dll（插件名 token 的 sha256 十六进制 + .dll）
规则（对齐 block.c 的 hit()）：token 名 -> sha256 -> <hash>.dll
零长名 token 不编译任何 DLL：e3b0c442….dll（sha256("")）已删除，零长名 → hit 失败 → 下钻空 key 编辑器块。
"""
import hashlib
import os
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
RL = os.path.join(ROOT, "raylib-6.0_win64_mingw-w64")
GCC = shutil.which("gcc") or "gcc"

# 原版插件：plugins\<文件>.c -> token（注意 in_int 的 token 是 "in-int"）
ORIGINAL = {
    "rerun": "rerun", "add": "add", "read": "read", "set": "set",
    "cond": "cond", "handrun": "handrun", "condrerun": "condrerun",
    "push_int": "push_int", "in_int": "in-int", "out": "out",
    "rand": "rand", "gt": "gt", "lt": "lt", "eq": "eq", "mul": "mul",
    "ret_int": "ret_int",
}

# 新增运算符插件：文件名 -> token
OPS = {'op_plus': '+', 'op_minus': '-', 'op_star': '*', 'op_div': '/', 'op_lt': '<', 'op_gt': '>', 'op_le': '<=', 'op_ge': '>=', 'op_eq': '==', 'op_ne': '!=', 'op_and': '&&', 'op_or': '||', 'op_not': '!', 'op_amp': '&', 'op_ior': '|=', 'op_inc': '++', 'op_dec': '--', 'op_iadd': '+=', 'op_qmark': '?', 'op_colon': ':', 'op_assign': '=', 'op_lbracket': '[', 'op_rbracket': ']', 'op_arrow': '->', 'op_dot': '.', 'g_set': 'SET'}

# 新增插件中需要 raylib 头/库的文件（其余为纯 C 自包含）
RAYLIB_FILES = ['BeginDrawing', 'BeginMode2D', 'CheckCollisionPointRec', 'ClearBackground', 'DrawLine', 'DrawLineV', 'DrawRectangle', 'DrawText', 'EndDrawing', 'EndMode2D', 'GetCharPressed', 'GetMouseDelta', 'GetMousePosition', 'GetMouseWheelMove', 'GetMouseX', 'GetMouseY', 'GetScreenHeight', 'GetScreenToWorld2D', 'GetScreenWidth', 'GetWindowHandle', 'InitWindow', 'IsKeyDown', 'IsKeyPressed', 'IsKeyReleased', 'IsMouseButtonDown', 'IsMouseButtonPressed', 'IsMouseButtonReleased', 'MeasureText', 'SetTargetFPS', 'SetTraceLogLevel', 'Vector2Add', 'Vector2Scale', 'Vector2Subtract', 'WindowShouldClose', 'gap_y', 'heat_color', 'item_color', 'item_w', 'nearest_gap', 'row_y']

# 编辑器插件（EState/editor_lib，经 raylib.h 类型与 raylib.dll 函数）
EDITOR_FILES = ['estate_new', 'build_lines', 'line_first', 'view_toks', 'update_completion', 'build_cands', 'pointer_locate', 'pointer_pos', 'hit_item', 'update_edit', 'space_insert', 'combo_insert', 'sel_copy', 'sel_del', 'paste', 'find_item_rect', 'drag_out', 'sync_views', 'draw_view', 'edit_append', 'inp_append', 'inp_backspace', 'frame_combo', 'frame_space', 'frame_focus', 'frame_left', 'frame_right', 'draw_input']
RAYLIB_FILES += EDITOR_FILES

# 新增插件中需要 user32 的文件
USER32_FILES = ['GetFileAttributesA', 'GetFocus', 'GetModuleHandleA', 'GetProcAddress', 'GetTickCount', 'SetFocus']


def dll_of(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest() + ".dll"


def sh(args, **kw):
    print(">", " ".join(args), flush=True)
    r = subprocess.run(args, cwd=ROOT, **kw)
    if r.returncode != 0:
        print("BUILD FAILED:", " ".join(args), file=sys.stderr)
        sys.exit(r.returncode)


def main():
    print("[1/7] gen_editor_blocks.py -> editor_blocks.h（纯 token 序列）")
    sh([sys.executable, "gen_editor_blocks.py"])

    print("[2/7] server.exe + upload_boot.exe")
    sh([GCC, "server.c", "-o", "server.exe", "-lws2_32"])
    sh([GCC, "upload_boot.c", "net.c", "-o", "upload_boot.exe", "-lws2_32"])

    print("[3/6] block.dll（执行器 + sha256 + 网络 + vmstate）")
    sh([GCC, "-shared", "-O2", "-I.", "block.c", "vmstate.c", "net.c", "sha256.c",
        "-o", "block.dll", "-Wl,--export-all-symbols,--out-implib,libblock.dll.a", "-lws2_32"])

    print("[4/6] 原版插件 plugins/*.c")
    for src, token in ORIGINAL.items():
        sh([GCC, "-shared", "-O2", "-I.", f"plugins/{src}.c", "-o", dll_of(token)])

    print("[5/6] 新增插件（现有 token 全集，不新增）")
    count = 0
    for f in sorted(os.listdir(os.path.join(ROOT, "plugins"))):
        if not f.endswith(".c"):
            continue
        stem = f[:-2]
        if stem in ORIGINAL:          # rand 等已在 [4/6] 构建
            continue
        token = OPS.get(stem, stem)   # 普通函数 token = 函数名
        args = [GCC, "-shared", "-O2", "-I.", f"plugins/{f}", "-o", dll_of(token)]
        if stem in RAYLIB_FILES:
            args += [f"-I{RL}/include", f"-L{RL}/lib", "-lraylibdll"]   # 链接 raylib.dll 导入库：多个插件共享同一 raylib 状态（窗口/GL 上下文跨插件）
        if stem in USER32_FILES:
            args += ["-luser32"]
        sh(args)
        count += 1
    print(f"    existing plugin files built: {count}")

    print("[6/6] vm.exe")
    sh([GCC, "vm.c", "-o", "vm.exe"])

    print("raylib.dll")
    try:
        shutil.copy2(os.path.join(RL, "lib", "raylib.dll"), os.path.join(ROOT, "raylib.dll"))
    except OSError as e:
        print(f"    warn: {e}")

    print("BUILD OK")


if __name__ == "__main__":
    main()
