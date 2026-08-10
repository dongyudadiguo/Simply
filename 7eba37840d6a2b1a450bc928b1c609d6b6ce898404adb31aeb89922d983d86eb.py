# push_int 插件：压入整数常量（payload=数字字符串）到栈（顶层执行，run_next 接棒）
import struct
import vmstate

v = int(payload.decode("utf-8","replace").strip())
vmstate.push(struct.pack("<I", v & 0xFFFFFFFF))
vmstate.write_num(4)
run_next()
