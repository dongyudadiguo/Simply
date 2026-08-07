# vm.py —— 虚拟机客户端（复用 block.py 公共逻辑，以 vm 的为准）
# 逻辑：block.run_loop 从空 key 引导 → 按 sha256 加载 .py 插件 → 无限执行
import os, sys              # 调整模块搜索路径（保证能找到 block.py）
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # 本目录加入搜索路径
from block import run_loop  # 公共：引导 + 无限执行（无错误处理）

if __name__ == "__main__":
    run_loop()              # 入口：从空 key 开始引导执行
