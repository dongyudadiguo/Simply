# 0ab2dd2f64c9fd4e4310cfbb82556f0596060583dec1a7ab2d178603c3eb61d0.py —— cond 插件：判断 stk 第一个字节，非零则 run_block 接棒到 payload 目标
import struct
import vmstate
from block import run_block

def run(payload=""):
    """payload = 目标 token 名；stk 首字节非零则 run_block 下钻"""
    ok = vmstate.stk_off > 0 and vmstate.stk[0] != 0
    if ok and payload: run_block(payload.encode())
    return ok
