# 8494db7bf4e15548b5190d1931af3def87cc6e78e65dd0063661f0152d34bf45.py —— condrerun 插件（顶层执行）
# stk 首字节非零 → 重跑当前块（读 vmstate.cur_key）
import vmstate

if vmstate.stk_off > 0 and vmstate.stk[0] != 0 and vmstate.cur_key:
    run_block(vmstate.cur_key)
run_next()   # 自主接棒到下一个 token
