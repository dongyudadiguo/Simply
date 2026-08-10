# add 插件：栈顶两个 u32 相加，结果覆盖写回，大小区记录 4（顶层直接执行，run_block 接棒）
# C 语义：*(u32*)stk = *(u32*)stk + *(u32*)(stk+4); n=4; *(u32*)num = n
import struct
import vmstate

o = vmstate.stk_off
a = struct.unpack_from("<I", vmstate.stk, o-8)[0]
b = struct.unpack_from("<I", vmstate.stk, o-4)[0]
struct.pack_into("<I", vmstate.stk, o-8, a + b)   # stk[栈顶] = a+b
vmstate.stk_off = o - 4                            # 两个变一个，栈回退 4
vmstate.write_num(4)                               # num 区记录结果大小
run_next()   # 自主接棒到下一个 token
