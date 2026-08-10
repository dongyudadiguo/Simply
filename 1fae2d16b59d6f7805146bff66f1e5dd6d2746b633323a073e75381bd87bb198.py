# 1fae2d16b59d6f7805146bff66f1e5dd6d2746b633323a073e75381bd87bb198.py —— rerun 插件（token="rerun" → sha256 命名）
# 内容：重跑当前块（自己所在的块）
# 直接代码：重跑当前块（reset 注入：位置重置回块头）
reset()                                 # 重跑当前块（职责分明：run_block 只管下钻）
