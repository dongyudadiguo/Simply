# vm.py —— 虚拟机客户端（复用 block.py 公共逻辑，以 vm 的为准）
# 逻辑：block.run_loop 从空 key 引导 → 按 sha256 加载 .py 插件 → 无限执行
from block import run_loop   # 同目录直接导入（主脚本目录自动在 sys.path[0]）

if __name__ == "__main__":
    run_loop()               # 入口：从空 key 开始引导执行
