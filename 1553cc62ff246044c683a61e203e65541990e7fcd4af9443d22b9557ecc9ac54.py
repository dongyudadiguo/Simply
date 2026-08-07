# 1553cc62ff246044c683a61e203e65541990e7fcd4af9443d22b9557ecc9ac54.py —— editor 插件（token="editor" → sha256 命名，独立于 boot）
# 内容：编辑器入口（显示/编辑块）。当前占位：print 一次后由 vm 重跑。
# 直接代码（不加 run 层）
from block import fetch, next_key   # 公共逻辑（vm 主脚本已把目录放入 sys.path）
import os, struct, hashlib

# 读取当前块（id key 引导块）展示
key = b""
p = fetch(key)
key = next_key(p)
print("editor: 当前块 token =", key, flush=True)
