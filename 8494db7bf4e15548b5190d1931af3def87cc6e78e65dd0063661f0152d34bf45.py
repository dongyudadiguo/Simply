# 8494db7bf4e15548b5190d1931af3def87cc6e78e65dd0063661f0152d34bf45.py —— condrerun 插件：判断 stk 第一个字节，非零则重跑当前块（rerun）
import inspect
import vmstate
from block import run_block

def run(payload=""):
    ok = vmstate.stk_off > 0 and vmstate.stk[0] != 0
    if ok:
        key = b""
        for f in inspect.stack()[1:]:
            if f.function == "run_block":
                key = f.frame.f_locals.get("start_key", b""); break
        run_block(key)
    return ok
