# rand 插件：payload="lo hi" 生成随机数压栈（默认 1 100；顶层执行，run_next 接棒）
import struct, random
import vmstate

s = payload.decode("utf-8","replace") if payload else "1 100"
parts = s.split()
lo = int(parts[0]) if len(parts) > 0 else 1
hi = int(parts[1]) if len(parts) > 1 else 100
v = random.randint(lo, hi)
vmstate.push(struct.pack("<I", v & 0xFFFFFFFF))
vmstate.write_num(4)
run_next()
