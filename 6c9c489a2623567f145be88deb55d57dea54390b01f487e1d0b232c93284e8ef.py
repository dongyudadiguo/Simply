# in-int 插件：读取用户整数输入压栈（顶层执行，run_next 接棒）
import struct
import vmstate

v = int(input().strip())
vmstate.push(struct.pack("<I", v & 0xFFFFFFFF))
vmstate.write_num(4)
run_next()
