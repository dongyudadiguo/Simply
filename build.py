#!/usr/bin/env python3
import hashlib, json, os, shutil, subprocess, sys
from pathlib import Path
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

def file_hash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def build(args, dependencies=()):
    output = args[args.index("-o") + 1]
    target = Path(ROOT, output)
    cache = Path(ROOT, ".build", output + ".json")
    inputs = [Path(ROOT, arg) for arg in args if arg.endswith(".c")]
    inputs.extend(Path(path) for path in dependencies)
    compiler = Path(GCC)
    signature = {
        "command": args,
        "compiler": file_hash(compiler) if compiler.is_file() else GCC,
        "inputs": {str(path): file_hash(path) for path in sorted(set(inputs))},
    }
    try:
        previous = json.loads(cache.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        previous = {}
    if (target.is_file() and previous.get("signature") == signature
            and previous.get("output") == file_hash(target)):
        print("SKIP", output, flush=True)
        return
    # Invalidate before compiling so a failed build cannot reuse old state.
    cache.parent.mkdir(exist_ok=True)
    cache.unlink(missing_ok=True)
    sh(args)
    cache.write_text(json.dumps({"signature": signature, "output": file_hash(target)},
                               indent=2), encoding="utf-8")

def copy_runtime():
    source = Path(RL, "lib", "raylib.dll")
    target = Path(ROOT, "raylib.dll")
    if not target.is_file() or file_hash(source) != file_hash(target):
        shutil.copy2(source, target)
        print("COPY raylib.dll", flush=True)
    else:
        print("SKIP raylib.dll", flush=True)

def main():
    local_headers = list(Path(ROOT).glob("*.h"))
    plugin_headers = local_headers + list(Path(ROOT, "plugins").rglob("*.h"))
    editor_dependencies = plugin_headers + list(Path(RL, "include").rglob("*.h"))
    editor_dependencies += list(Path(RL, "lib").glob("*.a"))
    editor_dependencies.append(Path(RL, "lib", "raylib.dll"))
    build([GCC, "server.c", "-o", "server.exe", "-lws2_32"], local_headers)
    editor = hashlib.sha256(b"").hexdigest() + ".dll"
    build([GCC, "-shared", "-O2", "-x", "c", "-I.", "-I"+os.path.join(RL,"include"), "plugins/.c",
        "-o", editor, "-L"+os.path.join(RL,"lib"), "-lraylibdll", "-lgdi32", "-lwinmm", "-lws2_32"], editor_dependencies)
    build([GCC, "vm.c", "-o", "vm.exe", "-lws2_32"], local_headers)
    copy_runtime()

    plugins_dir = os.path.join(ROOT, "plugins")
    for src, token in PLUGINS.items():
        src_path = os.path.join(plugins_dir, f"{src}.c")
        if os.path.exists(src_path):
            dll_name = hashlib.sha256(token.encode("utf-8")).hexdigest() + ".dll"
            build([GCC, "-shared", "-O2", "-I.", f"plugins/{src}.c", "-o", dll_name], plugin_headers)

    print("BUILD OK", editor)

if __name__ == "__main__":
    main()
