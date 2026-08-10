# mul 插件：栈顶两个 u32 相乘，结果覆盖写回，大小区记录 4（顶层执行，run_next 接棒）
import struct
import vmstate

o = vmstate.stk_off
a = struct.unpack_from("<I", vmstate.stk, o-8)[0]
b = struct.unpack_from("<I", vmstate.stk, o-4)[0]
struct.pack_into("<I", vmstate.stk, o-8, a * b)
vmstate.stk_off = o - 4
vmstate.write_num(4)
run_next()
