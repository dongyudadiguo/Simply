# 1fae2d16b59d6f7805146bff66f1e5dd6d2746b633323a073e75381bd87bb198.py —— rerun 插件（token="rerun" → sha256 命名）
# 内容：重跑当前块（自己所在的块）
# 直接代码：读 run_block 迭代主循环维护的 vmstate.cur_key = 当前块 key，再 run_block 重跑
import vmstate

run_block(vmstate.cur_key)            # 重跑当前块（迭代 run_block 闭包识别同 key → 重置位置）
