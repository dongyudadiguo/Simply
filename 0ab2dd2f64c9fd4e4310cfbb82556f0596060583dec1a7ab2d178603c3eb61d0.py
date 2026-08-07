# 0ab2dd2f64c9fd4e4310cfbb82556f0596060583dec1a7ab2d178603c3eb61d0.py —— cond 插件：判断 stk 第一个字节，非零则执行 payload 里的目标 token
import struct, importlib, os, hashlib
import vmstate
from block import HERE

def exec_plugin(token):
    path = os.path.join(HERE, hashlib.sha256(token.encode()).hexdigest()+".py")
    if os.path.exists(path):
        spec = importlib.util.spec_from_file_location("tok_"+token, path)
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        if hasattr(m, "run"): m.run()

def run(payload=""):
    """payload = 目标 token 名；stk 首字节非零则执行"""
    ok = vmstate.stk_off > 0 and vmstate.stk[0] != 0
    if ok and payload: exec_plugin(payload)
    return ok
