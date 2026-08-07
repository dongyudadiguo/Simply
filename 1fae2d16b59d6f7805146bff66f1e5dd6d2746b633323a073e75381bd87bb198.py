# 1fae2d16b59d6f7805146bff66f1e5dd6d2746b633323a073e75381bd87bb198.py —— rerun 插件（token="rerun" → sha256 命名）
# 内容：重跑当前块（自己所在的块）
# 直接代码：inspect 查调用栈中 run_loop 帧的 start_key = 当前块 key，再 run_loop 重跑
import inspect                       # 调用栈内省
from block import run_loop           # 公共逻辑（vm 主脚本已把目录放入 sys.path）

key = b""
for frame in inspect.stack()[1:]:    # 查最近的 run_loop 帧
    if frame.function == "run_loop":
        key = frame.frame.f_locals.get("start_key", b"")
        break
run_loop(key)                        # 重跑当前块
