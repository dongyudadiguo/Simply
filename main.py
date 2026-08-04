# main.py —— 最简 VM：解释当前块里的命令（editor / rerun）
# 当前块 = 一串 [4B长度][名字]；builtin 命令：
#   editor -> 显示当前块的内容（即所有命令名）
#   rerun  -> 直接重跑当前块
import struct
import boot_dll

MAX_RERUN = 3          # rerun 最多重跑几轮（设成 None 就是无限重跑）

def load_block():                      # 从服务端取当前块 -> 命令名列表
    p = boot_dll.fetch(boot_dll.get_id())
    cmds, i = [], 0
    while i + 4 <= len(p):
        n = struct.unpack("<I", p[i:i + 4])[0]; i += 4
        if n == 0:                     # 空块是分隔符/结束，跳过
            continue
        cmds.append(p[i:i + n].decode("utf-8", "replace")); i += n
    return cmds

def editor(block):
    print("当前块内容:", ", ".join(block))

def run_block(block, round=0):
    if MAX_RERUN is not None and round >= MAX_RERUN:
        print(f"已重跑 {MAX_RERUN} 轮，停止")
        return
    print(f"--- 运行当前块（第 {round + 1} 轮）---")
    for name in block:
        if name == "editor":
            editor(block)
        elif name == "rerun":
            print("rerun: 直接重跑当前块")
            run_block(block, round + 1)
            return

if __name__ == "__main__":
    run_block(load_block())
