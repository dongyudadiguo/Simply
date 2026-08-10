# vm.py —— 虚拟机客户端（复用 block.py 公共逻辑，以 vm 的为准）
# 逻辑：block.run_block 从空 key 引导 → 按 sha256 加载 .py 插件 → 无限执行
from block import run_block, exec_imp, find_plugin   # 同目录直接导入（主脚本目录自动在 sys.path[0]）

if __name__ == "__main__":
    imp = run_block()         # 先下钻到第一个命中插件的 token（对齐 runblock()）
    while True:               # 主循环：反复执行当前插件（对齐 while(1){exec(imp)}）
        if imp is None: break          # 全部走完 → 结束
        if not exec_imp(imp): break    # 插件主动结束（SystemExit）→ 保存退出
        imp = find_plugin()            # 下钻找下一个命中插件的 token
