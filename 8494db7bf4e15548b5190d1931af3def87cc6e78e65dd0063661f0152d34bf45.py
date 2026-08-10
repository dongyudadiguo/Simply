# 8494db7bf4e15548b5190d1931af3def87cc6e78e65dd0063661f0152d34bf45.py —— condrerun 插件（顶层执行）
# stk 首字节非零 → 重跑当前块（inspect 找 run_block 帧 start_key）
import inspect
import vmstate
from block import run_block

if vmstate.stk_off > 0 and vmstate.stk[0] != 0:
    key = b""
    for fr in inspect.stack()[1:]:
        if fr.function == "run_block":
            key = fr.frame.f_locals.get("start_key", b""); break
    if key:
        run_block(key)
run_next()   # 自主接棒到下一个 token
