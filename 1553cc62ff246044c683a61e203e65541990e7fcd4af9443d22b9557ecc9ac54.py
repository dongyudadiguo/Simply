# editor 插件（token="editor" → sha256 命名）
# 职责：vm 引导时启动一次 app_pyglet.py 编辑器。
#      用户关闭窗口后不再自动弹出（非守护）；vm 重启才重新启动。
import os, sys, time, subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
APP = os.path.join(HERE, "app_pyglet.py")
BLOCK = os.path.join(HERE, "_current_block.bin")
KEYF = os.path.join(HERE, "_current_key.txt")
_started = False

def run():
    global _started
    if _started:
        time.sleep(2)
        return
    env = dict(os.environ)
    env.pop("QT_QPA_PLATFORM", None)
    args = [sys.executable, APP]
    if os.path.exists(BLOCK) and os.path.exists(KEYF):
        args += [BLOCK, KEYF]
    subprocess.Popen(args, cwd=HERE, env=env)
    _started = True
    print("editor: 已启动 %s" % os.path.basename(APP), flush=True)
    time.sleep(2)
