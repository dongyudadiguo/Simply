#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成 editor_blocks.h。BLOCKS 为纯现有 token 序列。"""
import os

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "editor_blocks.h")

def u32(n):
    return int(n & 0xFFFFFFFF).to_bytes(4, "little")

import struct
import sys

class Stack:
    """简化栈模型：字节深度仿真。用于验证一个 token 序列在给定起始字节栈时是否下溢/净平衡。"""
    def __init__(self, depth=0, gvars=None):
        self.b = bytearray(b"\x00" * depth)
        self.gvars = dict(gvars or {})
    def push(self, n, val=None):
        if val is None:
            self.b += b"\x00" * n
        else:
            self.b += struct.pack("<I", int(val) & 0xFFFFFFFF)
    def pop(self, n):
        if len(self.b) < n:
            raise ValueError(f"stack underflow: pop {n} bytes, depth {len(self.b)}")
        self.b = self.b[:-n]
    def pop_u32(self):
        if len(self.b) < 4:
            raise ValueError("stack underflow: pop_u32")
        v = struct.unpack("<I", self.b[-4:])[0]
        self.b = self.b[:-4]
        return v
    @property
    def depth(self):
        return len(self.b)

def default_gvars():
    return {
        "estate": 8, "rk": 8, "rkn": 4,
        "bhb_n": 4, "bhb_a": 8,
        "bha_c": 4, "bha_n": 4, "bha_a": 8,
    }

def pstr(pay):
    return pay.decode("latin1") if isinstance(pay, bytes) else pay

def apply_token(s, name, pay):
    """把 token 栈效应作用到 Stack；不处理 call/cond/rerun（由 check_tokens 处理）。"""
    if name == "GET":
        s.push(4, 0)
    elif name == "SET":
        s.pop_u32()
    elif name == "GV":
        key = pstr(pay)
        s.push(8)
        s.push(4, s.gvars.get(key, 0))
    elif name == "GVSET":
        n = s.pop_u32()
        s.pop(n)
        s.gvars[pstr(pay)] = n
    elif name == "ld":
        n = s.pop_u32()
        s.pop(8)
        s.push(n)
    elif name == "st":
        n = s.pop_u32()
        s.pop(8)
        s.pop(n)
    elif name == "push_int":
        raw = pstr(pay).split("\x00", 1)[0]
        s.push(4, int(raw or "0"))
    elif name == "push_payload":
        s.push(len(pay))
    elif name == "push_payload_ptr":
        s.push(8)
    elif name == "drop":
        s.pop(4)
    elif name == "padd":
        s.pop(4); s.pop(8); s.push(8)
    elif name == "calloc":
        s.pop(4); s.pop(4); s.push(8)
    elif name == "memcpy":
        s.pop(4); s.pop(8); s.pop(8); s.push(8)
    elif name in ("strcpy", "strcat"):
        s.pop(8); s.pop(8); s.push(8)
    elif name == "cur_root_of":
        s.push(8); s.push(4, 32)
    elif name == "!":
        s.pop(4); s.push(4)
    elif name in ("+", "-", ">", "<", ">=", "<=", "!=", "&&", "/", "|", "&", "==", "*",
                  "mul", "gt", "lt", "eq"):
        s.pop(4); s.pop(4); s.push(4)
    elif name in ("fgt", "fge", "flt", "fle"):
        s.pop(4); s.pop(4); s.push(4)
    elif name == "exit":
        s.pop(4)
    elif name == "IsKeyPressed":
        s.pop(4); s.push(4)
    elif name == "BeginMode2D":
        s.pop(24)
    elif name == "ClearBackground":
        s.pop(4)
    elif name in ("GetScreenWidth", "GetScreenHeight", "GetMouseX", "GetMouseY",
                  "GetCharPressed", "GetMouseWheelMove"):
        s.push(4)
    elif name in ("fdiv", "fadd", "fmul", "fsub"):
        s.pop(4); s.pop(4); s.push(4)
    elif name in ("f2i", "i2f"):
        s.pop(4); s.push(4)
    elif name in ("GetMousePosition", "GetMouseDelta"):
        s.push(8)
    elif name == "GetScreenToWorld2D":
        s.pop(24); s.pop(8); s.push(8)
    elif name in ("Vector2Subtract", "Vector2Add"):
        s.pop(8); s.pop(8); s.push(8)
    elif name == "Vector2Scale":
        s.pop(4); s.pop(8); s.push(8)
    elif name == "DrawLineV":
        s.pop(4); s.pop(8); s.pop(8)
    elif name == "DrawText":
        s.pop(4 + 4 + 4 + 4 + 8)
    elif name == "WindowShouldClose":
        s.push(4)
    elif name in ("SetTraceLogLevel", "SetTargetFPS", "srand"):
        s.pop(4)
    elif name == "IsMouseButtonDown":
        s.pop(4); s.push(4)
    elif name == "InitWindow":
        s.pop(4); s.pop(4)
    elif name == "GetTickCount":
        s.push(4)
    elif name == "GetWindowHandle":
        s.push(8)
    elif name == "SetFocus":
        s.pop(8); s.push(8)
    # 当前仍存在的编辑器封壳：记录其旧 DLL 的栈效应，便于未来并对替换序列。
    elif name == "hit_view":
        s.pop(8); s.pop(8); s.push(4)
    elif name in ("draw_view", "edit_append"):
        s.pop(8); s.pop(4)
    elif name == "pointer_locate":
        s.pop(8); s.push(4)
    elif name in ("update_edit", "update_completion", "frame_combo", "frame_space",
                  "frame_left", "frame_right", "sync_views", "compact_views"):
        s.pop(8)
    else:
        raise ValueError(f"no stack model for token {name!r}")

def check_tokens(tokens, depth=0, gvars=None):
    """验证一个独立块：cond 按 false 分支（只清条件，不跳目标），call/rerun 不改变栈。"""
    s = Stack(depth=depth, gvars=gvars)
    for name, pay in tokens:
        name = pstr(name)
        if name in ("call", "rerun", "BeginDrawing", "EndDrawing", "EndMode2D"):
            continue
        if name == "cond":
            if s.depth >= 4:
                s.pop(4)
            continue
        apply_token(s, name, pay)
    return s

def check_all_blocks():
    print("[stack-check] cond=false-branch, call no-op (argument blocks will be noise)")
    by_key = dict(BLOCKS)
    for key, _klen, _ident, _ln in KEYS:
        key = pstr(key)
        try:
            s = check_tokens(by_key[key], gvars=default_gvars())
            status = f"ok depth={s.depth}" if s.depth == 0 else f"NONZERO depth={s.depth}"
            print(f"  {key!r:16} {status}")
        except Exception as e:
            print(f"  {key!r:16} ERROR {e}")


KEYS = [
    ('', 0, "BLK_MAIN", 1830),
    ('ei', 2, "BLK_ei", 1236),
    ('quit', 4, "BLK_quit", 34),
    ('bin', 3, "BLK_bin", 200),
    ('bbk', 3, "BLK_bbk", 45),
    ('bch', 3, "BLK_bch", 211),
    ('bche', 4, "BLK_bche", 77),
    ('bcam', 4, "BLK_bcam", 746),
    ('bwhl', 4, "BLK_bwhl", 1513),
    ('bpan', 4, "BLK_bpan", 535),
    ('bvw', 3, "BLK_bvw", 51),
    ('bvwc', 4, "BLK_bvwc", 130),
    ('bvwb', 4, "BLK_bvwb", 129),
    ('bcv0', 4, "BLK_bcv0", 107),
    ('bdi', 3, "BLK_bdi", 325),
    ('bhb', 3, "BLK_bhb", 130),
    ('bhb1', 4, "BLK_bhb1", 460),
    ('bha', 3, "BLK_bha", 167),
    ('bha1', 4, "BLK_bha1", 719),
    ('bfocus', 6, "BLK_bfocus", 384),
    ('bfocus_do', 9, "BLK_bfocus_do", 67),
    ('hv', 2, "BLK_hv", 207),
    ('hvc', 3, "BLK_hvc", 128),
    ('hvb', 3, "BLK_hvb", 1159),
    ('hvs', 3, "BLK_hvs", 48),
    ('hvn', 3, "BLK_hvn", 73),
    ('hvf', 3, "BLK_hvf", 18),
]

BLOCKS = [
    ('', [
        (b'GET', b'inited'),
        (b'!', b''),
        (b'cond', b'ei'),
        (b'call', b'bin'),
        (b'call', b'bcam'),
        (b'GV', b'estate'),
        (b'ld', b''),
        (b'push_int', b'24\x00'),
        (b'padd', b''),
        (b'push_int', b'8\x00'),
        (b'ld', b''),
        (b'GV', b'estate'),
        (b'ld', b''),
        (b'call', b'hv'),
        (b'GV', b'estate'),
        (b'ld', b''),
        (b'push_int', b'44\x00'),
        (b'padd', b''),
        (b'push_int', b'4\x00'),
        (b'st', b''),
        (b'GV', b'estate'),
        (b'ld', b''),
        (b'push_int', b'44\x00'),
        (b'padd', b''),
        (b'push_int', b'4\x00'),
        (b'ld', b''),
        (b'GV', b'estate'),
        (b'ld', b''),
        (b'push_int', b'26876\x00'),
        (b'padd', b''),
        (b'push_int', b'4\x00'),
        (b'ld', b''),
        (b'>', b''),
        (b'cond', b'bcv0'),
        (b'GV', b'estate'),
        (b'ld', b''),
        (b'update_edit', b''),
        (b'GV', b'estate'),
        (b'ld', b''),
        (b'frame_combo', b''),
        (b'GV', b'estate'),
        (b'ld', b''),
        (b'frame_space', b''),
        (b'push_int', b'256\x00'),
        (b'IsKeyPressed', b''),
        (b'cond', b'quit'),
        (b'GV', b'estate'),
        (b'ld', b''),
        (b'call', b'bfocus'),
        (b'GV', b'estate'),
        (b'ld', b''),
        (b'frame_left', b''),
        (b'GV', b'estate'),
        (b'ld', b''),
        (b'frame_right', b''),
        (b'BeginDrawing', b''),
        (b'push_payload', b'\x0f\x12\x18\xff'),
        (b'ClearBackground', b''),
        (b'GV', b'estate'),
        (b'ld', b''),
        (b'push_int', b'0\x00'),
        (b'padd', b''),
        (b'push_int', b'24\x00'),
        (b'ld', b''),
        (b'BeginMode2D', b''),
        (b'call', b'bvw'),
        (b'GV', b'estate'),
        (b'ld', b''),
        (b'pointer_locate', b''),
        (b'drop', b''),
        (b'GV', b'estate'),
        (b'ld', b''),
        (b'push_int', b'590640\x00'),
        (b'padd', b''),
        (b'push_int', b'8\x00'),
        (b'ld', b''),
        (b'GV', b'estate'),
        (b'ld', b''),
        (b'push_int', b'8\x00'),
        (b'padd', b''),
        (b'push_int', b'4\x00'),
        (b'ld', b''),
        (b'GetScreenWidth', b''),
        (b'push_int', b'2\x00'),
        (b'/', b''),
        (b'i2f', b''),
        (b'GV', b'estate'),
        (b'ld', b''),
        (b'push_int', b'20\x00'),
        (b'padd', b''),
        (b'push_int', b'4\x00'),
        (b'ld', b''),
        (b'fdiv', b''),
        (b'fadd', b''),
        (b'GV', b'estate'),
        (b'ld', b''),
        (b'push_int', b'590644\x00'),
        (b'padd', b''),
        (b'push_int', b'4\x00'),
        (b'ld', b''),
        (b'push_payload', b'\x00\xe40\xff'),
        (b'DrawLineV', b''),
        (b'EndMode2D', b''),
        (b'GV', b'estate'),
        (b'ld', b''),
        (b'push_int', b'572'),
        (b'padd', b''),
        (b'push_int', b'4'),
        (b'ld', b''),
        (b'push_int', b'0'),
        (b'>', b''),
        (b'cond', b'bdi'),
        (b'EndDrawing', b''),
        (b'GV', b'estate'),
        (b'ld', b''),
        (b'sync_views', b''),
        (b'GV', b'estate'),
        (b'ld', b''),
        (b'compact_views', b''),
        (b'WindowShouldClose', b''),
        (b'cond', b'quit'),
        (b'rerun', b''),
    ]),
    ('ei', [
        (b'push_int', b'1'),
        (b'push_int', b'592704'),
        (b'calloc', b''),
        (b'push_int', b'8'),
        (b'GVSET', b'estate'),
        (b'push_payload', b'\x00\x00 B\x00\x00pB'),
        (b'GV', b'estate'),
        (b'ld', b''),
        (b'push_int', b'9216'),
        (b'padd', b''),
        (b'push_int', b'8'),
        (b'st', b''),
        (b'push_int', b'4294967295'),
        (b'GV', b'estate'),
        (b'ld', b''),
        (b'push_int', b'9224'),
        (b'padd', b''),
        (b'push_int', b'4'),
        (b'st', b''),
        (b'push_int', b'4294967295'),
        (b'GV', b'estate'),
        (b'ld', b''),
        (b'push_int', b'9228'),
        (b'padd', b''),
        (b'push_int', b'4'),
        (b'st', b''),
        (b'push_int', b'1'),
        (b'GV', b'estate'),
        (b'ld', b''),
        (b'push_int', b'26876'),
        (b'padd', b''),
        (b'push_int', b'4'),
        (b'st', b''),
        (b'cur_root_of', b''),
        (b'drop', b''),
        (b'push_int', b'8'),
        (b'GVSET', b'rk'),
        (b'cur_root_of', b''),
        (b'push_int', b'4'),
        (b'GVSET', b'rkn'),
        (b'drop', b''),
        (b'drop', b''),
        (b'GV', b'estate'),
        (b'ld', b''),
        (b'push_int', b'8956'),
        (b'padd', b''),
        (b'GV', b'rk'),
        (b'ld', b''),
        (b'GV', b'rkn'),
        (b'ld', b''),
        (b'memcpy', b''),
        (b'drop', b''),
        (b'drop', b''),
        (b'GV', b'rkn'),
        (b'ld', b''),
        (b'GV', b'estate'),
        (b'ld', b''),
        (b'push_int', b'9212'),
        (b'padd', b''),
        (b'push_int', b'4'),
        (b'st', b''),
        (b'push_payload', b'\x00\x00\x80?'),
        (b'GV', b'estate'),
        (b'ld', b''),
        (b'push_int', b'20\x00'),
        (b'padd', b''),
        (b'push_int', b'4\x00'),
        (b'st', b''),
        (b'push_int', b'0\x00'),
        (b'SetTraceLogLevel', b''),
        (b'push_int', b'1000\x00'),
        (b'push_int', b'700\x00'),
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
        (b'push_int', b'259\x00'),
        (b'IsKeyPressed', b''),
        (b'cond', b'bbk'),
        (b'GV', b'estate'),
        (b'ld', b''),
        (b'update_completion', b''),
    ]),
    ('bbk', [
        (b'GV', b'estate'),
        (b'ld', b''),
        (b'call', b'bhb'),
    ]),
    ('bch', [
        (b'GV', b'estate'),
        (b'ld', b''),
        (b'push_int', b'52\x00'),
        (b'padd', b''),
        (b'push_int', b'4\x00'),
        (b'ld', b''),
        (b'push_int', b'4294967295\x00'),
        (b'!=', b''),
        (b'cond', b'bche'),
        (b'GET', b'ch'),
        (b'GV', b'estate'),
        (b'ld', b''),
        (b'call', b'bha'),
        (b'call', b'bin'),
    ]),
    ('bche', [
        (b'GET', b'ch'),
        (b'GV', b'estate'),
        (b'ld', b''),
        (b'edit_append', b''),
        (b'call', b'bin'),
    ]),
    ('bcam', [
        (b'GetMouseWheelMove', b''),
        (b'GV', b'estate'),
        (b'ld', b''),
        (b'push_int', b'590652\x00'),
        (b'padd', b''),
        (b'push_int', b'4\x00'),
        (b'st', b''),
        (b'GV', b'estate'),
        (b'ld', b''),
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
        (b'GV', b'estate'),
        (b'ld', b''),
        (b'push_int', b'0\x00'),
        (b'padd', b''),
        (b'push_int', b'8\x00'),
        (b'st', b''),
        (b'GetMousePosition', b''),
        (b'GV', b'estate'),
        (b'ld', b''),
        (b'push_int', b'0\x00'),
        (b'padd', b''),
        (b'push_int', b'24\x00'),
        (b'ld', b''),
        (b'GetScreenToWorld2D', b''),
        (b'GV', b'estate'),
        (b'ld', b''),
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
        (b'GV', b'estate'),
        (b'ld', b''),
        (b'push_int', b'590660\x00'),
        (b'padd', b''),
        (b'push_int', b'8\x00'),
        (b'st', b''),
        (b'GV', b'estate'),
        (b'ld', b''),
        (b'push_int', b'590660\x00'),
        (b'padd', b''),
        (b'push_int', b'8\x00'),
        (b'ld', b''),
        (b'GV', b'estate'),
        (b'ld', b''),
        (b'push_int', b'0\x00'),
        (b'padd', b''),
        (b'push_int', b'24\x00'),
        (b'ld', b''),
        (b'GetScreenToWorld2D', b''),
        (b'GV', b'estate'),
        (b'ld', b''),
        (b'push_int', b'590668\x00'),
        (b'padd', b''),
        (b'push_int', b'8\x00'),
        (b'st', b''),
        (b'GV', b'estate'),
        (b'ld', b''),
        (b'push_int', b'20\x00'),
        (b'padd', b''),
        (b'push_int', b'4\x00'),
        (b'ld', b''),
        (b'GV', b'estate'),
        (b'ld', b''),
        (b'push_int', b'590652\x00'),
        (b'padd', b''),
        (b'push_int', b'4\x00'),
        (b'ld', b''),
        (b'push_payload', b'\xcd\xcc\xcc='),
        (b'fmul', b''),
        (b'fmul', b''),
        (b'GV', b'estate'),
        (b'ld', b''),
        (b'push_int', b'20\x00'),
        (b'padd', b''),
        (b'push_int', b'4\x00'),
        (b'ld', b''),
        (b'fadd', b''),
        (b'GV', b'estate'),
        (b'ld', b''),
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
        (b'GV', b'estate'),
        (b'ld', b''),
        (b'push_int', b'0\x00'),
        (b'padd', b''),
        (b'push_int', b'8\x00'),
        (b'st', b''),
        (b'GV', b'estate'),
        (b'ld', b''),
        (b'push_int', b'590668\x00'),
        (b'padd', b''),
        (b'push_int', b'8\x00'),
        (b'ld', b''),
        (b'GV', b'estate'),
        (b'ld', b''),
        (b'push_int', b'590660\x00'),
        (b'padd', b''),
        (b'push_int', b'8\x00'),
        (b'ld', b''),
        (b'GV', b'estate'),
        (b'ld', b''),
        (b'push_int', b'0\x00'),
        (b'padd', b''),
        (b'push_int', b'24\x00'),
        (b'ld', b''),
        (b'GetScreenToWorld2D', b''),
        (b'Vector2Subtract', b''),
        (b'GV', b'estate'),
        (b'ld', b''),
        (b'push_int', b'8\x00'),
        (b'padd', b''),
        (b'push_int', b'8\x00'),
        (b'ld', b''),
        (b'Vector2Add', b''),
        (b'GV', b'estate'),
        (b'ld', b''),
        (b'push_int', b'8\x00'),
        (b'padd', b''),
        (b'push_int', b'8\x00'),
        (b'st', b''),
    ]),
    ('bpan', [
        (b'GetMouseDelta', b''),
        (b'push_payload', b'\x00\x00\x80?'),
        (b'GV', b'estate'),
        (b'ld', b''),
        (b'push_int', b'20\x00'),
        (b'padd', b''),
        (b'push_int', b'4\x00'),
        (b'ld', b''),
        (b'fdiv', b''),
        (b'Vector2Scale', b''),
        (b'GV', b'estate'),
        (b'ld', b''),
        (b'push_int', b'590676\x00'),
        (b'padd', b''),
        (b'push_int', b'8\x00'),
        (b'st', b''),
        (b'GV', b'estate'),
        (b'ld', b''),
        (b'push_int', b'8\x00'),
        (b'padd', b''),
        (b'push_int', b'8\x00'),
        (b'ld', b''),
        (b'GV', b'estate'),
        (b'ld', b''),
        (b'push_int', b'590676\x00'),
        (b'padd', b''),
        (b'push_int', b'8\x00'),
        (b'ld', b''),
        (b'Vector2Subtract', b''),
        (b'GV', b'estate'),
        (b'ld', b''),
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
        (b'GV', b'estate'),
        (b'ld', b''),
        (b'push_int', b'26876\x00'),
        (b'padd', b''),
        (b'push_int', b'4\x00'),
        (b'ld', b''),
        (b'<', b''),
        (b'cond', b'bvwb'),
    ]),
    ('bvwb', [
        (b'GET', b'vi'),
        (b'GV', b'estate'),
        (b'ld', b''),
        (b'draw_view', b''),
        (b'GET', b'vi'),
        (b'push_int', b'1\x00'),
        (b'+', b''),
        (b'SET', b'vi'),
        (b'call', b'bvwc'),
    ]),
    ('bcv0', [
        (b'push_int', b'0\x00'),
        (b'GV', b'estate'),
        (b'ld', b''),
        (b'push_int', b'44\x00'),
        (b'padd', b''),
        (b'push_int', b'4\x00'),
        (b'st', b''),
    ]),
    ('bdi', [
        (b'GV', b'estate'),
        (b'ld', b''),
        (b'push_int', b'590652'),
        (b'padd', b''),
        (b'GV', b'estate'),
        (b'ld', b''),
        (b'push_int', b'316'),
        (b'padd', b''),
        (b'strcpy', b''),
        (b'GV', b'estate'),
        (b'ld', b''),
        (b'push_int', b'576'),
        (b'padd', b''),
        (b'strcat', b''),
        (b'GetMouseX', b''),
        (b'push_int', b'20'),
        (b'+', b''),
        (b'GetMouseY', b''),
        (b'push_int', b'20'),
        (b'push_payload', b'\xe8\xec\xef\xff'),
        (b'DrawText', b''),
    ]),
    ('bhb', [
        (b'GV', b'estate'),
        (b'ld', b''),
        (b'push_int', b'572'),
        (b'padd', b''),
        (b'push_int', b'4'),
        (b'ld', b''),
        (b'push_int', b'0'),
        (b'>', b''),
        (b'cond', b'bhb1'),
    ]),
    ('bhb1', [
        (b'GV', b'estate'),
        (b'ld', b''),
        (b'push_int', b'572'),
        (b'padd', b''),
        (b'push_int', b'4'),
        (b'ld', b''),
        (b'push_int', b'1'),
        (b'-', b''),
        (b'push_int', b'4'),
        (b'GVSET', b'bhb_n'),
        (b'GV', b'bhb_n'),
        (b'ld', b''),
        (b'GV', b'estate'),
        (b'ld', b''),
        (b'push_int', b'572'),
        (b'padd', b''),
        (b'push_int', b'4'),
        (b'st', b''),
        (b'GV', b'estate'),
        (b'ld', b''),
        (b'push_int', b'316'),
        (b'padd', b''),
        (b'GV', b'bhb_n'),
        (b'ld', b''),
        (b'padd', b''),
        (b'push_int', b'8'),
        (b'GVSET', b'bhb_a'),
        (b'push_payload', b'\x00'),
        (b'GV', b'bhb_a'),
        (b'ld', b''),
        (b'push_int', b'1'),
        (b'st', b''),
    ]),
    ('bha', [
        (b'push_int', b'4'),
        (b'GVSET', b'bha_c'),
        (b'GV', b'estate'),
        (b'ld', b''),
        (b'push_int', b'572'),
        (b'padd', b''),
        (b'push_int', b'4'),
        (b'ld', b''),
        (b'push_int', b'250'),
        (b'<', b''),
        (b'cond', b'bha1'),
    ]),
    ('bha1', [
        (b'GV', b'estate'),
        (b'ld', b''),
        (b'push_int', b'572'),
        (b'padd', b''),
        (b'push_int', b'4'),
        (b'ld', b''),
        (b'push_int', b'1'),
        (b'+', b''),
        (b'push_int', b'4'),
        (b'GVSET', b'bha_n'),
        (b'GV', b'bha_n'),
        (b'ld', b''),
        (b'GV', b'estate'),
        (b'ld', b''),
        (b'push_int', b'572'),
        (b'padd', b''),
        (b'push_int', b'4'),
        (b'st', b''),
        (b'GV', b'estate'),
        (b'ld', b''),
        (b'push_int', b'316'),
        (b'padd', b''),
        (b'GV', b'bha_n'),
        (b'ld', b''),
        (b'push_int', b'1'),
        (b'-', b''),
        (b'padd', b''),
        (b'push_int', b'8'),
        (b'GVSET', b'bha_a'),
        (b'GV', b'bha_c'),
        (b'ld', b''),
        (b'push_int', b'1'),
        (b'ld', b''),
        (b'GV', b'bha_a'),
        (b'ld', b''),
        (b'push_int', b'1'),
        (b'st', b''),
        (b'GV', b'estate'),
        (b'ld', b''),
        (b'push_int', b'316'),
        (b'padd', b''),
        (b'GV', b'bha_n'),
        (b'ld', b''),
        (b'padd', b''),
        (b'push_int', b'8'),
        (b'GVSET', b'bha_a'),
        (b'push_payload', b'\x00'),
        (b'GV', b'bha_a'),
        (b'ld', b''),
        (b'push_int', b'1'),
        (b'st', b''),
    ]),
    ('bfocus', [
        (b'drop', b''),
        (b'drop', b''),
        (b'GetMouseX', b''),
        (b'push_int', b'0'),
        (b'>=', b''),
        (b'SET', b'bfc1'),
        (b'GetMouseY', b''),
        (b'push_int', b'0'),
        (b'>=', b''),
        (b'SET', b'bfc2'),
        (b'GetMouseX', b''),
        (b'GetScreenWidth', b''),
        (b'<', b''),
        (b'SET', b'bfc3'),
        (b'GetMouseY', b''),
        (b'GetScreenHeight', b''),
        (b'<', b''),
        (b'SET', b'bfc4'),
        (b'GET', b'bfc1'),
        (b'GET', b'bfc2'),
        (b'&&', b''),
        (b'GET', b'bfc3'),
        (b'&&', b''),
        (b'GET', b'bfc4'),
        (b'&&', b''),
        (b'cond', b'bfocus_do'),
    ]),
    ('bfocus_do', [
        (b'GetWindowHandle', b''),
        (b'SetFocus', b''),
        (b'drop', b''),
        (b'drop', b''),
    ]),
    ('hv', [
        (b'drop', b''),
        (b'drop', b''),
        (b'drop', b''),
        (b'drop', b''),
        (b'push_int', b'4294967295'),
        (b'SET', b'hvh'),
        (b'GV', b'estate'),
        (b'ld', b''),
        (b'push_int', b'26876'),
        (b'padd', b''),
        (b'push_int', b'4'),
        (b'ld', b''),
        (b'SET', b'hvi'),
        (b'call', b'hvc'),
    ]),
    ('hvc', [
        (b'GET', b'hvi'),
        (b'push_int', b'0'),
        (b'>', b''),
        (b'SET', b'hvc0'),
        (b'GET', b'hvc0'),
        (b'cond', b'hvb'),
        (b'GET', b'hvc0'),
        (b'!', b''),
        (b'cond', b'hvf'),
    ]),
    ('hvb', [
        (b'GET', b'hvi'),
        (b'push_int', b'1'),
        (b'-', b''),
        (b'SET', b'hvid'),
        (b'GV', b'estate'),
        (b'ld', b''),
        (b'push_int', b'24'),
        (b'padd', b''),
        (b'push_int', b'4'),
        (b'ld', b''),
        (b'GV', b'estate'),
        (b'ld', b''),
        (b'GET', b'hvid'),
        (b'push_int', b'280'),
        (b'mul', b''),
        (b'padd', b''),
        (b'push_int', b'8956'),
        (b'padd', b''),
        (b'push_int', b'260'),
        (b'padd', b''),
        (b'push_int', b'4'),
        (b'ld', b''),
        (b'push_payload', b'\x00\x00\xa0A'),
        (b'fsub', b''),
        (b'fge', b''),
        (b'SET', b'hvx'),
        (b'GV', b'estate'),
        (b'ld', b''),
        (b'push_int', b'28'),
        (b'padd', b''),
        (b'push_int', b'4'),
        (b'ld', b''),
        (b'GV', b'estate'),
        (b'ld', b''),
        (b'GET', b'hvid'),
        (b'push_int', b'280'),
        (b'mul', b''),
        (b'padd', b''),
        (b'push_int', b'8956'),
        (b'padd', b''),
        (b'push_int', b'264'),
        (b'padd', b''),
        (b'push_int', b'4'),
        (b'ld', b''),
        (b'push_payload', b'\x00\x00\xc0@'),
        (b'fsub', b''),
        (b'fge', b''),
        (b'SET', b'hvy'),
        (b'GV', b'estate'),
        (b'ld', b''),
        (b'push_int', b'28'),
        (b'padd', b''),
        (b'push_int', b'4'),
        (b'ld', b''),
        (b'GV', b'estate'),
        (b'ld', b''),
        (b'GET', b'hvid'),
        (b'push_int', b'280'),
        (b'mul', b''),
        (b'padd', b''),
        (b'push_int', b'8956'),
        (b'padd', b''),
        (b'push_int', b'276'),
        (b'padd', b''),
        (b'push_int', b'4'),
        (b'ld', b''),
        (b'push_payload', b'\x00\x00\xc0@'),
        (b'fadd', b''),
        (b'fle', b''),
        (b'SET', b'hvz'),
        (b'GET', b'hvx'),
        (b'GET', b'hvy'),
        (b'&&', b''),
        (b'GET', b'hvz'),
        (b'&&', b''),
        (b'SET', b'hvhit'),
        (b'GET', b'hvhit'),
        (b'cond', b'hvs'),
        (b'GET', b'hvhit'),
        (b'!', b''),
        (b'cond', b'hvn'),
    ]),
    ('hvs', [
        (b'GET', b'hvid'),
        (b'SET', b'hvh'),
        (b'call', b'hvf'),
    ]),
    ('hvn', [
        (b'GET', b'hvi'),
        (b'push_int', b'1'),
        (b'-', b''),
        (b'SET', b'hvi'),
        (b'call', b'hvc'),
    ]),
    ('hvf', [
        (b'GET', b'hvh'),
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
    if len(sys.argv) > 1 and sys.argv[1] == "check":
        check_all_blocks()
    else:
        text = generate()
        with open(OUT, "w", encoding="utf-8") as f:
            f.write(text)
        print(f"wrote {OUT}")




