# vm.py —— 虚拟机客户端（复用 block.py 公共逻辑，以 vm 的为准）
# 逻辑：block.run_block 从空 key 引导 → 按 sha256 加载 .py 插件 → 无限执行
import block                                    # 同目录直接导入（读全局 imp/env）

if __name__ == "__main__":
    block.run_block()                  # runblock()：下钻设置首个 imp
    while True:                        # while(1){exec(imp)} —— 零错误处理，异常直接冒泡
        exec(block.imp, block.env)     # 只这一行：执行当前插件（imp/env 由 run_next/run_block 更新）
