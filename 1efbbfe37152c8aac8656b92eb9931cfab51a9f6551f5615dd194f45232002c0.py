# 1efbbfe37152c8aac8656b92eb9931cfab51a9f6551f5615dd194f45232002c0.py —— handrun 插件（顶层执行）
# payload = 8字节id + 目标token；按钮只改 id 指向的 flags（vmstate.hand_flags），这里按 flags 执行
import vmstate

target = payload[8:].decode("utf-8","replace") if len(payload) >= 8 else ""
if target:
    f = vmstate.hand_flags.get(payload[:8], [0, 0])
    if f[0]:
        f[0] = 0; vmstate.hand_flags[payload[:8]] = f    # b1 执行一次（清 0）
        run_block(target.encode())
    if f[1]:
        run_block(target.encode())                        # b2 持续执行
run_next()   # 自主接棒到下一个 token
