# 1fae2d16b59d6f7805146bff66f1e5dd6d2746b633323a073e75381bd87bb198.py —— rerun 插件（token="rerun" → sha256 命名）
# 语义：重跑当前块（自己所在的块）
# 实现：inspect 查调用栈中最近的 run_loop 帧，取其 start_key 参数 = 当前块 key
import inspect          # 调用栈内省
import os, sys          # 调整模块搜索路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # 本目录加入搜索路径
from block import run_loop   # 公共：引导 + 无限执行

def _current_block_key():
    """查最近的 run_loop 帧的 start_key = 当前块 key（不改 block.py）"""
    for frame in inspect.stack()[1:]:
        if frame.function == "run_loop":
            return frame.f_locals.get("start_key", b"")
    return b""

def run():
    run_loop(_current_block_key())   # 重跑当前块
