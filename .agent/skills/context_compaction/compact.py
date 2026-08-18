# compact.py — 备份对话，压成一条 user，然后立刻杀掉 ae.py
"""把 json.input 整段换成一条 user 摘要，并终止对应的 ae.py。

在工具里调用（会杀掉当前 runner，这一轮不会再写 function_call_output）：

    from skills.context_compaction import compact_and_stop
    compact_and_stop("摘要文本")

指定文件：

    compact_and_stop("摘要文本", r"C:\\...\\input_新对话.json")

命令行：

    python -m skills.context_compaction.compact --summary "摘要文本"
    python -m skills.context_compaction.compact input_新对话.json --summary "摘要文本"
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import signal
import subprocess
import sys
from datetime import datetime
from pathlib import Path

# skills/context_compaction/compact.py → responses/
ROOT = Path(__file__).resolve().parents[2]
SUMMARY_PREFIX = "[Compacted context summary; archived messages were replaced locally]"


def _atomic_write(path: Path, data: dict) -> None:
    temp = path.with_name(f"{path.name}.{os.getpid()}.compact.tmp")
    try:
        temp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(temp, path)
    finally:
        if temp.exists():
            temp.unlink()


def _is_system_item(item) -> bool:
    return isinstance(item, dict) and item.get("role") == "system"


def _leading_system_items(items):
    kept = []
    for item in items:
        if not _is_system_item(item):
            break
        kept.append(item)
    return kept


def _summary_item(summary: str) -> dict:
    text = SUMMARY_PREFIX + "\n\n" + summary.strip()
    return {"role": "user", "content": [{"type": "input_text", "text": text}]}


def _pid_file_for(input_path: Path) -> Path:
    return input_path.parent / ".ae_runners" / f"{input_path.name}.pid"


def _read_runner_pid(input_path: Path):
    path = _pid_file_for(input_path)
    try:
        raw = path.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    if not raw:
        return None
    try:
        info = json.loads(raw)
    except json.JSONDecodeError:
        info = None
    if isinstance(info, dict):
        try:
            return int(info.get("pid"))
        except (TypeError, ValueError):
            return None
    try:
        return int(raw)
    except ValueError:
        return None


def _cmdline(pid: int):
    try:
        import psutil

        return psutil.Process(pid).cmdline()
    except Exception:
        return []


def _looks_like_ae(pid: int) -> bool:
    if pid <= 0 or pid == os.getpid():
        return False
    cmd = _cmdline(pid)
    if cmd:
        return any(Path(part).name.lower() == "ae.py" for part in cmd)
    return os.environ.get("AE_RUNNER") == "1"


def _collect_runner_pids(input_path: Path) -> list[int]:
    pids = []
    seen = set()

    def add(pid):
        try:
            pid = int(pid)
        except (TypeError, ValueError):
            return
        if pid <= 0 or pid == os.getpid() or pid in seen:
            return
        seen.add(pid)
        pids.append(pid)

    file_pid = _read_runner_pid(input_path)
    if file_pid:
        add(file_pid)

    if os.environ.get("AE_RUNNER") == "1":
        parent = os.getppid()
        if _looks_like_ae(parent) or file_pid is None:
            add(parent)

    return pids


def _kill_pid_tree(pid: int) -> bool:
    if pid <= 0 or pid == os.getpid():
        return False
    if os.name == "nt":
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        result = subprocess.run(
            ["taskkill", "/PID", str(pid), "/T", "/F"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=flags,
        )
        return result.returncode == 0
    try:
        import psutil

        parent = psutil.Process(pid)
        kids = parent.children(recursive=True)
        for child in kids:
            try:
                child.terminate()
            except psutil.Error:
                pass
        try:
            parent.terminate()
        except psutil.Error:
            pass
        gone, alive = psutil.wait_procs(kids + [parent], timeout=1.5)
        for leftover in alive:
            try:
                leftover.kill()
            except psutil.Error:
                pass
        return True
    except Exception:
        try:
            os.kill(pid, signal.SIGTERM)
            return True
        except OSError:
            return False


def _stop_runner(input_path: Path) -> dict:
    pids = _collect_runner_pids(input_path)
    killed = []
    for pid in pids:
        if _kill_pid_tree(pid):
            killed.append(pid)
    pid_file = _pid_file_for(input_path)
    try:
        pid_file.unlink()
    except OSError:
        pass
    return {"pids": pids, "killed": killed}


def resolve_input_path(input_path=None) -> Path:
    if input_path:
        path = Path(input_path).expanduser().resolve()
        if not path.is_file():
            raise FileNotFoundError(path)
        return path
    env_path = (os.environ.get("AE_INPUT_FILE") or "").strip()
    if env_path:
        path = Path(env_path).expanduser().resolve()
        if path.is_file():
            return path
    for cand in (Path.cwd() / "input.json", ROOT / "input.json"):
        if cand.is_file():
            return cand.resolve()
    raise FileNotFoundError("找不到 input.json：请传入路径或设置 AE_INPUT_FILE")


def compact_file(input_path, summary: str) -> dict:
    path = resolve_input_path(input_path)
    text = summary.strip() if isinstance(summary, str) else ""
    if not text:
        raise ValueError("summary 为空")

    data = json.loads(path.read_text(encoding="utf-8"))
    body = data.get("json")
    if not isinstance(body, dict) or not isinstance(body.get("input"), list):
        raise ValueError("不是 Responses 格式（缺少 json.input）")

    items = body["input"]
    kept_system = _leading_system_items(items)
    compacted = kept_system + [_summary_item(text)]
    before_messages = len(items)
    before_bytes = path.stat().st_size
    body["input"] = compacted

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = path.with_name(f"{path.name}.precompact-{stamp}.bak")
    shutil.copy2(path, backup)
    _atomic_write(path, data)
    after_bytes = path.stat().st_size

    return {
        "path": str(path),
        "backup": str(backup),
        "messages_before": before_messages,
        "messages_after": len(compacted),
        "bytes_before": before_bytes,
        "bytes_after": after_bytes,
        "kept_system": len(kept_system),
    }


def compact_and_stop(summary: str, input_path=None) -> dict:
    """备份、压成一条 user，然后杀掉 ae.py，避免它再追加 function_call_output。"""
    path = resolve_input_path(input_path)
    result = compact_file(path, summary)
    result["stopped"] = _stop_runner(path)
    try:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        sys.stdout.flush()
        sys.stderr.flush()
    except (OSError, ValueError):
        pass
    # 工具跑在 driver 子进程里：只 exit 自己的话，ae.py 仍会读盘并写回 output。
    # 上面已经 taskkill 了 ae.py 进程树；这里再兜底，防止杀进程失败时把结果返回给 ae.py。
    os._exit(0)
    return result  # noqa: unreachable


def main(argv=None):
    parser = argparse.ArgumentParser(description="备份并压缩 ae.py 对话，然后终止 runner")
    parser.add_argument("input_json", nargs="?", default=None, help="默认 AE_INPUT_FILE / ./input.json")
    parser.add_argument("--summary", required=True, help="压成一条 user 的摘要正文")
    parser.add_argument(
        "--keep-running",
        action="store_true",
        help="只压缩不杀进程（ae.py 仍可能追加当前这条 function_call_output）",
    )
    args = parser.parse_args(argv)
    if args.keep_running:
        print(json.dumps(compact_file(args.input_json, args.summary), ensure_ascii=False, indent=2))
        return
    compact_and_stop(args.summary, args.input_json)


if __name__ == "__main__":
    main()
