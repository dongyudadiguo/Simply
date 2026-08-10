# vm.py —— 虚拟机客户端（复用 block.py 公共逻辑，以 vm 的为准）
# 逻辑：block.run_block 从空 key 引导 → 按 sha256 加载 .py 插件 → 无限执行
import block
from block import run_next, run_block, reset   # 放进当前作用域（exec(block.imp) 单参数能查到）

block.run_block()                      # runblock()：下钻设置首个 imp
while True:                            # while(1){exec(imp)} —— 零错误处理，异常直接冒泡
    exec(block.imp)                    # 只执行当前插件（payload 已拼进 imp，run_next/run_block/reset 更新 imp）
