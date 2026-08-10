# vmstate.py —— VM 运行时共享状态（read/set 等指令插件的内存）
# stk: 值栈 | num: 大小区 | var: 变量区，记录 = [name][nsize u32][vptr 8B][vsize u32]
stk = bytearray(4096); num = bytearray(512); var = bytearray(8192)
stk_off = num_off = var_off = 0

def push(data):                        # 值压栈（stk 推进）
    global stk_off
    stk[stk_off:stk_off+len(data)] = data
    stk_off += len(data)

def pop(n):                            # 弹栈 n 字节
    global stk_off
    stk_off -= n
    return bytes(stk[stk_off:stk_off+n])

def write_num(size):                   # 记录结果大小到 num 区
    global num_off
    num[num_off:num_off+4] = size.to_bytes(4, "little")
    num_off += 4

hand_flags = {}                              # handrun id(bytes) -> [b1, b2]（editor 按钮写、插件读）
