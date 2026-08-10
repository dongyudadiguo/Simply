# 1efbbfe37152c8aac8656b92eb9931cfab51a9f6551f5615dd194f45232002c0.py —— handrun 插件：payload = 8字节id + 目标token
# id 索引两个布尔（初始0）：b1 执行一次（检查到1清0再执行）、b2 执行（检查到1执行）
import vmstate
from block import run_block

flags = {}                                    # id(bytes) -> [b1, b2]

def run(payload=b""):
    if len(payload) < 8: return
    hid, token = payload[:8], payload[8:].decode("utf-8","replace")
    f = flags.setdefault(hid, [0, 0])
    if token:
        if f[0]: f[0] = 0; run_block(token.encode())   # 执行一次（清 0）
        if f[1]: run_block(token.encode())             # 执行（保持 1）
