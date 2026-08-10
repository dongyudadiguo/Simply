# out 插件：打印 payload 文本；无 payload 打印栈顶 u32（顶层执行，run_next 接棒）
import struct
import vmstate

if payload:
    print(payload.decode("utf-8","replace"), end="")
else:
    v = struct.unpack_from("<I", vmstate.stk, vmstate.stk_off-4)[0]
    print(v, end="")
run_next()
