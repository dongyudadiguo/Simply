# 1553cc62....py —— editor 插件（token="editor" → sha256 命名，独立于 boot）
# 语义：编辑器入口（显示/编辑块）。与 boot（引导器）是不同的插件。
# 当前：复用公共 run_loop 引导执行；后续可在此实现编辑器逻辑（GUI/显示）。
import os, sys                       # 调整模块搜索路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # 本目录加入搜索路径
from block import run_loop           # 公共：引导 + 无限执行

def run():
    run_loop()                       # 编辑器入口：先复用引导执行（占位）
