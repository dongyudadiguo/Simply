# 6ee0eb490ff832101cf82a3d387c35f29e4230be786978f7acf9e811febf6723.py —— set 插件（变量名在右 → 登记栈顶，顶层执行）
# 语义：把当前 stk 值登记为变量（name+nsize+vptr+vsize），stk/num 推进（对应 C 的 var 登记 + stk += numsize）
import struct
import vmstate

name = payload.encode() if isinstance(payload, str) else payload
var = vmstate.var
v = vmstate.var_off
numsize = struct.unpack_from("<I", vmstate.num, vmstate.num_off - 4)[0]  # 结果大小（刚写入）
var[v:v+len(name)] = name; v += len(name)                 # name
struct.pack_into("<I", var, v, len(name)); v += 4         # nsize
struct.pack_into("<Q", var, v, vmstate.stk_off - numsize); v += 8   # vptr = 值起始
struct.pack_into("<I", var, v, numsize); v += 4           # vsize
vmstate.var_off = v
vmstate.stk_off += numsize                                # 栈推进（值已登记）
vmstate.num_off += 4                                      # 大小区推进
run_next()   # 自主接棒到下一个 token
