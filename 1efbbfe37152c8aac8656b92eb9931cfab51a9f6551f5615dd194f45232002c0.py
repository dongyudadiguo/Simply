# 1efbbfe37152c8aac8656b92eb9931cfab51a9f6551f5615dd194f45232002c0.py —— handrun 插件（顶层执行）
# payload = 8字节id + 目标token；run_block 下钻执行目标块
from block import run_block

target = payload[8:].decode("utf-8","replace") if len(payload) >= 8 else ""
if target:
    run_block(target.encode())
