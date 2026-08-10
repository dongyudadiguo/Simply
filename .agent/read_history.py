# read_history.py —— 读取历史 input.json 备份里"用户说过的话"
# 用法：
#   python read_history.py list                 # 列出所有备份
#   python read_history.py <备份文件>            # 提取该备份所有用户消息（时间顺序）
#   python read_history.py latest                # 提取最新备份的用户消息
import json, glob, sys, os
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

def user_texts(path):
    data = json.load(open(path, encoding="utf-8"))
    items = data["json"]["input"]
    out = []
    for it in items:
        if it.get("role") != "user":
            continue
        c = it.get("content")
        if not isinstance(c, list):
            continue
        for part in c:
            if part.get("type") == "input_text":
                t = part.get("text", "")
                if not t or t.startswith("[Compacted context summary"):
                    continue
                out.append(t)
    return out

def main():
    args = sys.argv[1:]
    baks = sorted(glob.glob(os.path.join(os.path.dirname(os.path.abspath(__file__)), "input.json.precompact-*.bak")))
    if not args or args[0] == "list":
        for b in baks:
            print(os.path.basename(b), os.path.getsize(b)//1024, "KB")
        return
    target = args[0]
    if target == "latest":
        path = baks[-1] if baks else None
    else:
        path = target if os.path.exists(target) else os.path.join(os.path.dirname(os.path.abspath(__file__)), target)
    if not path or not os.path.exists(path):
        print("找不到:", target); return
    texts = user_texts(path)
    print("=== %s：%d 条用户消息 ===" % (os.path.basename(path), len(texts)))
    for i, t in enumerate(texts, 1):
        t = t.replace("\n", " ")
        print("[%d] %s" % (i, t[:600]))

if __name__ == "__main__":
    main()
