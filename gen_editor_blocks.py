#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成 editor_blocks.h。

这里的 BLOCKS 是纯数据：每块 = key + token 序列。
每个 token = (token名, payload)。不包含任何 E()/st()/ld() 辅助封装，
只是把已经存在的 token 按序编码成块字节并写出 C 头文件。
"""
import os

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "editor_blocks.h")

def u32(n):
    """4 字节小端无符号整数。仅用于 token payload 里的整数。"""
    return int(n & 0xFFFFFFFF).to_bytes(4, "little")

KEYS = [
    ('', 0, "BLK_MAIN", 1512),
    ('ei', 2, "BLK_ei", 327),
    ('quit', 4, "BLK_quit", 34),
    ('bin', 3, "BLK_bin", 188),
    ('bbk', 3, "BLK_bbk", 39),
    ('bch', 3, "BLK_bch", 190),
    ('bche', 4, "BLK_bche", 65),
    ('bcam', 4, "BLK_bcam", 686),
    ('bwhl', 4, "BLK_bwhl", 1345),
    ('bpan', 4, "BLK_bpan", 475),
    ('bvw', 3, "BLK_bvw", 51),
    ('bvwc', 4, "BLK_bvwc", 118),
    ('bvwb', 4, "BLK_bvwb", 117),
    ('bcv0', 4, "BLK_bcv0", 95),
]

BLOCKS = [
    ('', [
        (b'GET', b'inited'),
        (b'!', b''),
        (b'cond', b'ei'),
        (b'call', b'bin'),
        (b'call', b'bcam'),
        (b'estate', b''),
        (b'push_int', b'24\x00'),
        (b'padd', b''),
        (b'push_int', b'8\x00'),
        (b'ld', b''),
        (b'estate', b''),
        (b'hit_view', b''),
        (b'estate', b''),
        (b'push_int', b'44\x00'),
        (b'padd', b''),
        (b'push_int', b'4\x00'),
        (b'st', b''),
        (b'estate', b''),
        (b'push_int', b'44\x00'),
        (b'padd', b''),
        (b'push_int', b'4\x00'),
        (b'ld', b''),
        (b'estate', b''),
        (b'push_int', b'26876\x00'),
        (b'padd', b''),
        (b'push_int', b'4\x00'),
        (b'ld', b''),
        (b'>', b''),
        (b'cond', b'bcv0'),
        (b'estate', b''),
        (b'update_edit', b''),
        (b'estate', b''),
        (b'frame_combo', b''),
        (b'estate', b''),
        (b'frame_space', b''),
        (b"push_int", u32(0x00363532)),
        (b'IsKeyPressed', b''),
        (b'cond', b'quit'),
        (b'estate', b''),
        (b'frame_focus', b''),
        (b'estate', b''),
        (b'frame_left', b''),
        (b'estate', b''),
        (b'frame_right', b''),
        (b'BeginDrawing', b''),
        (b'push_payload', b'\x0f\x12\x18\xff'),
        (b'ClearBackground', b''),
        (b'estate', b''),
        (b'push_int', b'0\x00'),
        (b'padd', b''),
        (b'push_int', b'24\x00'),
        (b'ld', b''),
        (b'BeginMode2D', b''),
        (b'call', b'bvw'),
        (b'estate', b''),
        (b'pointer_locate', b''),
        (b'drop', b''),
        (b'estate', b''),
        (b'push_int', b'590640\x00'),
        (b'padd', b''),
        (b'push_int', b'8\x00'),
        (b'ld', b''),
        (b'estate', b''),
        (b'push_int', b'8\x00'),
        (b'padd', b''),
        (b'push_int', b'4\x00'),
        (b'ld', b''),
        (b'GetScreenWidth', b''),
        (b'push_int', b'2\x00'),
        (b'/', b''),
        (b'i2f', b''),
        (b'estate', b''),
        (b'push_int', b'20\x00'),
        (b'padd', b''),
        (b'push_int', b'4\x00'),
        (b'ld', b''),
        (b'fdiv', b''),
        (b'fadd', b''),
        (b'estate', b''),
        (b'push_int', b'590644\x00'),
        (b'padd', b''),
        (b'push_int', b'4\x00'),
        (b'ld', b''),
        (b'push_payload', b'\x00\xe40\xff'),
        (b'DrawLineV', b''),
        (b'EndMode2D', b''),
        (b'estate', b''),
        (b'draw_input', b''),
        (b'EndDrawing', b''),
        (b'estate', b''),
        (b'sync_views', b''),
        (b'estate', b''),
        (b'compact_views', b''),
        (b'WindowShouldClose', b''),
        (b'cond', b'quit'),
        (b'rerun', b''),
    ]),
    ('ei', [
        (b'estate_new', b''),
        (b'push_payload', b'\x00\x00\x80?'),
        (b'estate', b''),
        (b'push_int', b'20\x00'),
        (b'padd', b''),
        (b'push_int', b'4\x00'),
        (b'st', b''),
        (b'push_int', b'0\x00'),
        (b'SetTraceLogLevel', b''),
        (b'push_int', b'1000\x00'),
        (b"push_int", u32(0x00303037)),
        (b'InitWindow', b''),
        (b'push_int', b'60\x00'),
        (b'SetTargetFPS', b''),
        (b'GetTickCount', b''),
        (b'srand', b''),
        (b'push_int', b'1\x00'),
        (b'SET', b'inited'),
    ]),
    ('quit', [
        (b'push_int', b'0\x00'),
        (b'exit', b''),
    ]),
    ('bin', [
        (b'GetCharPressed', b''),
        (b'SET', b'ch'),
        (b'GET', b'ch'),
        (b'push_int', b'0\x00'),
        (b'>', b''),
        (b'cond', b'bch'),
        (b"push_int", u32(0x00393532)),
        (b'IsKeyPressed', b''),
        (b'cond', b'bbk'),
        (b'estate', b''),
        (b'update_completion', b''),
    ]),
    ('bbk', [
        (b'estate', b''),
        (b'inp_backspace', b''),
    ]),
    ('bch', [
        (b'estate', b''),
        (b'push_int', b'52\x00'),
        (b'padd', b''),
        (b'push_int', b'4\x00'),
        (b'ld', b''),
        (b'push_int', b'4294967295\x00'),
        (b'!=', b''),
        (b'cond', b'bche'),
        (b'GET', b'ch'),
        (b'estate', b''),
        (b'inp_append', b''),
        (b'call', b'bin'),
    ]),
    ('bche', [
        (b'GET', b'ch'),
        (b'estate', b''),
        (b'edit_append', b''),
        (b'call', b'bin'),
    ]),
    ('bcam', [
        (b'GetMouseWheelMove', b''),
        (b'estate', b''),
        (b'push_int', b'590652\x00'),
        (b'padd', b''),
        (b'push_int', b'4\x00'),
        (b'st', b''),
        (b'estate', b''),
        (b'push_int', b'590652\x00'),
        (b'padd', b''),
        (b'push_int', b'4\x00'),
        (b'ld', b''),
        (b'f2i', b''),
        (b'push_int', b'0\x00'),
        (b'!=', b''),
        (b'cond', b'bwhl'),
        (b'GetScreenWidth', b''),
        (b'push_int', b'2\x00'),
        (b'/', b''),
        (b'i2f', b''),
        (b'GetScreenHeight', b''),
        (b'push_int', b'2\x00'),
        (b'/', b''),
        (b'i2f', b''),
        (b'estate', b''),
        (b'push_int', b'0\x00'),
        (b'padd', b''),
        (b'push_int', b'8\x00'),
        (b'st', b''),
        (b'GetMousePosition', b''),
        (b'estate', b''),
        (b'push_int', b'0\x00'),
        (b'padd', b''),
        (b'push_int', b'24\x00'),
        (b'ld', b''),
        (b'GetScreenToWorld2D', b''),
        (b'estate', b''),
        (b'push_int', b'24\x00'),
        (b'padd', b''),
        (b'push_int', b'8\x00'),
        (b'st', b''),
        (b'push_int', b'2\x00'),
        (b'IsMouseButtonDown', b''),
        (b'cond', b'bpan'),
    ]),
    ('bwhl', [
        (b'GetMousePosition', b''),
        (b'estate', b''),
        (b'push_int', b'590660\x00'),
        (b'padd', b''),
        (b'push_int', b'8\x00'),
        (b'st', b''),
        (b'estate', b''),
        (b'push_int', b'590660\x00'),
        (b'padd', b''),
        (b'push_int', b'8\x00'),
        (b'ld', b''),
        (b'estate', b''),
        (b'push_int', b'0\x00'),
        (b'padd', b''),
        (b'push_int', b'24\x00'),
        (b'ld', b''),
        (b'GetScreenToWorld2D', b''),
        (b'estate', b''),
        (b'push_int', b'590668\x00'),
        (b'padd', b''),
        (b'push_int', b'8\x00'),
        (b'st', b''),
        (b'estate', b''),
        (b'push_int', b'20\x00'),
        (b'padd', b''),
        (b'push_int', b'4\x00'),
        (b'ld', b''),
        (b'estate', b''),
        (b'push_int', b'590652\x00'),
        (b'padd', b''),
        (b'push_int', b'4\x00'),
        (b'ld', b''),
        (b'push_payload', b'\xcd\xcc\xcc='),
        (b'fmul', b''),
        (b'fmul', b''),
        (b'estate', b''),
        (b'push_int', b'20\x00'),
        (b'padd', b''),
        (b'push_int', b'4\x00'),
        (b'ld', b''),
        (b'fadd', b''),
        (b'estate', b''),
        (b'push_int', b'20\x00'),
        (b'padd', b''),
        (b'push_int', b'4\x00'),
        (b'st', b''),
        (b'GetScreenWidth', b''),
        (b'push_int', b'2\x00'),
        (b'/', b''),
        (b'i2f', b''),
        (b'GetScreenHeight', b''),
        (b'push_int', b'2\x00'),
        (b'/', b''),
        (b'i2f', b''),
        (b'estate', b''),
        (b'push_int', b'0\x00'),
        (b'padd', b''),
        (b'push_int', b'8\x00'),
        (b'st', b''),
        (b'estate', b''),
        (b'push_int', b'590668\x00'),
        (b'padd', b''),
        (b'push_int', b'8\x00'),
        (b'ld', b''),
        (b'estate', b''),
        (b'push_int', b'590660\x00'),
        (b'padd', b''),
        (b'push_int', b'8\x00'),
        (b'ld', b''),
        (b'estate', b''),
        (b'push_int', b'0\x00'),
        (b'padd', b''),
        (b'push_int', b'24\x00'),
        (b'ld', b''),
        (b'GetScreenToWorld2D', b''),
        (b'Vector2Subtract', b''),
        (b'estate', b''),
        (b'push_int', b'8\x00'),
        (b'padd', b''),
        (b'push_int', b'8\x00'),
        (b'ld', b''),
        (b'Vector2Add', b''),
        (b'estate', b''),
        (b'push_int', b'8\x00'),
        (b'padd', b''),
        (b'push_int', b'8\x00'),
        (b'st', b''),
    ]),
    ('bpan', [
        (b'GetMouseDelta', b''),
        (b'push_payload', b'\x00\x00\x80?'),
        (b'estate', b''),
        (b'push_int', b'20\x00'),
        (b'padd', b''),
        (b'push_int', b'4\x00'),
        (b'ld', b''),
        (b'fdiv', b''),
        (b'Vector2Scale', b''),
        (b'estate', b''),
        (b'push_int', b'590676\x00'),
        (b'padd', b''),
        (b'push_int', b'8\x00'),
        (b'st', b''),
        (b'estate', b''),
        (b'push_int', b'8\x00'),
        (b'padd', b''),
        (b'push_int', b'8\x00'),
        (b'ld', b''),
        (b'estate', b''),
        (b'push_int', b'590676\x00'),
        (b'padd', b''),
        (b'push_int', b'8\x00'),
        (b'ld', b''),
        (b'Vector2Subtract', b''),
        (b'estate', b''),
        (b'push_int', b'8\x00'),
        (b'padd', b''),
        (b'push_int', b'8\x00'),
        (b'st', b''),
    ]),
    ('bvw', [
        (b'push_int', b'0\x00'),
        (b'SET', b'vi'),
        (b'call', b'bvwc'),
    ]),
    ('bvwc', [
        (b'GET', b'vi'),
        (b'estate', b''),
        (b'push_int', b'26876\x00'),
        (b'padd', b''),
        (b'push_int', b'4\x00'),
        (b'ld', b''),
        (b'<', b''),
        (b'cond', b'bvwb'),
    ]),
    ('bvwb', [
        (b'GET', b'vi'),
        (b'estate', b''),
        (b'draw_view', b''),
        (b'GET', b'vi'),
        (b'push_int', b'1\x00'),
        (b'+', b''),
        (b'SET', b'vi'),
        (b'call', b'bvwc'),
    ]),
    ('bcv0', [
        (b'push_int', b'0\x00'),
        (b'estate', b''),
        (b'push_int', b'44\x00'),
        (b'padd', b''),
        (b'push_int', b'4\x00'),
        (b'st', b''),
    ]),
]

def encode_block(tokens):
    out = bytearray()
    for name, pay in tokens:
        out += u32(len(name))
        out += name
        out += u32(len(pay))
        out += pay
    out += b"\xff\xff\xff\xff"
    return bytes(out)

def fmt_bytes(data, indent="    ", per_line=12):
    rows = []
    cur = []
    for b in data:
        cur.append(f"0x{b:02x}")
        if len(cur) == per_line:
            rows.append(indent + ",".join(cur) + ",")
            cur = []
    if cur:
        rows.append(indent + ",".join(cur) + ",")
    return "\n".join(rows)

def generate():
    o = []
    o.append("/* editor_blocks.h —— 由 gen_editor_blocks.py 生成：纯现有 token 序列 */")
    o.append("#ifndef EDITOR_BLOCKS_H")
    o.append("#define EDITOR_BLOCKS_H")
    o.append("#include <stdint.h>")
    o.append("")
    for key, klen, ident, ln in KEYS:
        data = encode_block(dict(BLOCKS)[key])
        flow = " ".join(f"{n.decode('latin1')}<{len(p)}>" for n,p in dict(BLOCKS)[key])
        o.append(f"/* {ident}: key={key!r} klen={klen}, {len(data)} bytes, {len(dict(BLOCKS)[key])} tokens")
        o.append("   flow: " + flow)
        o.append("*/")
        o.append(f"static const uint8_t {ident}[{len(data)}] = {{")
        o.append(fmt_bytes(data))
        o.append("};")
        o.append("")
    o.append("static const struct { const char *key; uint32_t klen; const uint8_t *data; uint32_t len; } EDITOR_BLOCKS[] = {")
    for key, klen, ident, ln in KEYS:
        o.append(f"    {{\"{key}\", {klen}, {ident}, {ln}}},")
    o.append("};")
    o.append("#define EDITOR_BLOCKS_N (sizeof(EDITOR_BLOCKS)/sizeof(EDITOR_BLOCKS[0]))")
    o.append("#endif")
    return "\n".join(o) + "\n"

if __name__ == "__main__":
    text = generate()
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(text)
    print(f"wrote {OUT}")
