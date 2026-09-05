#!/usr/bin/env python3
import hashlib, os, shutil, subprocess, sys
ROOT = os.path.dirname(os.path.abspath(__file__))
RL = os.path.join(ROOT, "raylib-6.0_win64_mingw-w64")
GCC = shutil.which("gcc") or "gcc"

PLUGINS = {
    "get": "get",
    "set": "set",
    "gget": "gget",
    "gset": "gset",
    "cond": "cond",
    "condrerun": "condrerun",
    "handrun": "handrun",
    "rerun": "rerun",
    "add": "add",
    "init": "init"
}

def sh(args):
    print(">", " ".join(args), flush=True)
    r = subprocess.run(args, cwd=ROOT)
    if r.returncode: sys.exit(r.returncode)

def main():
    sh([GCC, "server.c", "-o", "server.exe", "-lws2_32"])
    editor = hashlib.sha256(b"").hexdigest() + ".dll"
    sh([GCC, "-shared", "-O2", "-x", "c", "-I.", "-I"+os.path.join(RL,"include"), ".c",
        "-o", editor, "-L"+os.path.join(RL,"lib"), "-lraylibdll", "-lgdi32", "-lwinmm", "-lws2_32"])
    sh([GCC, "vm.c", "-o", "vm.exe", "-lws2_32"])
    shutil.copy2(os.path.join(RL,"lib","raylib.dll"), os.path.join(ROOT,"raylib.dll"))

    plugins_dir = os.path.join(ROOT, "plugins")
    for src, token in PLUGINS.items():
        src_path = os.path.join(plugins_dir, f"{src}.c")
        if os.path.exists(src_path):
            dll_name = hashlib.sha256(token.encode("utf-8")).hexdigest() + ".dll"
            sh([GCC, "-shared", "-O2", "-I.", f"plugins/{src}.c", "-o", dll_name])

    print("BUILD OK", editor)

if __name__ == "__main__":
    main()
