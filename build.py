#!/usr/bin/env python3
import hashlib, os, shutil, subprocess, sys
ROOT = os.path.dirname(os.path.abspath(__file__))
RL = os.path.join(ROOT, "raylib-6.0_win64_mingw-w64")
GCC = shutil.which("gcc") or "gcc"
def sh(args):
    print(">", " ".join(args), flush=True)
    r = subprocess.run(args, cwd=ROOT)
    if r.returncode: sys.exit(r.returncode)
def main():
    sh([GCC, "server.c", "-o", "server.exe", "-lws2_32"])
    editor = hashlib.sha256(b"").hexdigest() + ".dll"
    sh([GCC, "-shared", "-O2", "-x", "c", "-I.", "-I"+os.path.join(RL,"include"), ".c",
        "-o", editor, "-L"+os.path.join(RL,"lib"), "-lraylibdll", "-lgdi32", "-lwinmm"])
    sh([GCC, "vm.c", "-o", "vm.exe", "-lws2_32"])
    shutil.copy2(os.path.join(RL,"lib","raylib.dll"), os.path.join(ROOT,"raylib.dll"))
    print("BUILD OK", editor)
if __name__ == "__main__":
    main()
