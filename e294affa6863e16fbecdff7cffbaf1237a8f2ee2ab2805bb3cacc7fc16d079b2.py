# gt 插件：栈顶两 u32 比较 a>b → 压 1 否则 0（顶层执行，run_next 接棒）
import struct
import vmstate

o = vmstate.stk_off
a = struct.unpack_from("<I", vmstate.stk, o-8)[0]
b = struct.unpack_from("<I", vmstate.stk, o-4)[0]
r = 1 if a > b else 0
struct.pack_into("<I", vmstate.stk, o-8, r)
vmstate.stk_off = o - 4
vmstate.write_num(4)
run_next()
