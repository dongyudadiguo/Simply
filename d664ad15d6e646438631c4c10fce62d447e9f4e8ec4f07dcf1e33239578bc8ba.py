# ret_int 插件：结束执行（返回）；payload 非空打印 payload，空则打印栈顶（顶层执行，退出）
import struct
import vmstate

if payload:
    print(payload.decode("utf-8","replace"))
elif vmstate.stk_off >= 4:
    print(struct.unpack_from("<I", vmstate.stk, vmstate.stk_off-4)[0])
raise SystemExit(0)
