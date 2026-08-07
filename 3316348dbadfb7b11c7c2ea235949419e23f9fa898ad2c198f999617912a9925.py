# 3316348dbadfb7b11c7c2ea235949419e23f9fa898ad2c198f999617912a9925.py —— read 插件（变量名在左 → 压栈）
# 语义：从 var 区反向找同名变量，把值拷贝到 stk（对应 C：memcmp 匹配后 memcpy(stk_off, vptr, vsize)）
import struct
import vmstate

def read(name):
    name = name.encode() if isinstance(name, str) else name
    v = vmstate.var_off                      # 从 var 末尾反向扫描
    while v > 0:
        nsize = struct.unpack_from("<I", vmstate.var, v-16)[0]
        vptr  = struct.unpack_from("<Q", vmstate.var, v-12)[0]
        vsize = struct.unpack_from("<I", vmstate.var, v-4)[0]
        if vmstate.var[v-16-nsize:v-16] == name:   # 名字匹配
            vmstate.push(bytes(vmstate.stk[vptr:vptr+vsize]))  # 值在 stk（vptr 是 stk 偏移）
            return
        v -= 16 + nsize
    raise KeyError(name)
