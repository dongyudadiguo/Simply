# Context Compaction

备份 `input.json`（或指定 json），把 `json.input` 整段换成一条 user 摘要，然后立刻杀掉对应的 `ae.py`。

## 规则
1. 只动 `json.input`；`url` / `headers` / `model` / `tools` 不动。
2. 保留开头的 `system` 项。
3. 先写 `*.precompact-时间戳.bak`，再原子替换。
4. 必须杀掉 **ae.py 进程树**，不能只 exit driver，否则 ae.py 会把当前 `function_call_output` 钉在摘要后面。
5. 摘要只留高信号：当前目标、路径、架构、已完成、验证、下一步。不要凭据和日志。

## 用法
工具内（压当前对话并停）：

```python
from skills.context_compaction import compact_and_stop
compact_and_stop("""摘要""")
```

指定文件：

```python
from skills.context_compaction import compact_and_stop
compact_and_stop("摘要", r"C:\Users\12159\Desktop\ai_exec\responses\input_新对话.json")
```

命令行：

```text
python -m skills.context_compaction.compact --summary "摘要"
python -m skills.context_compaction.compact input_新对话.json --summary "摘要"
```

只压缩不杀进程（一般不要用）：`--keep-running`
