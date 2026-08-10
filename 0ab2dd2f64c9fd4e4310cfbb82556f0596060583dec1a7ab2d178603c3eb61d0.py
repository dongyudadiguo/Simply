# 0ab2dd2f64c9fd4e4310cfbb82556f0596060583dec1a7ab2d178603c3eb61d0.py —— cond 插件（顶层执行）
# stk 首字节非零 → run_block 下钻到 payload 目标 token
import vmstate
from block import run_block

if vmstate.stk_off > 0 and vmstate.stk[0] != 0 and payload:
    run_block(payload.encode())
