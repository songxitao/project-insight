# T2 — 扩展 `local_graph.py`：import 目标存在性回查

**What to build:** 在现有 `local_graph.py` 的 `scan_imports` 基础上，对每个被识别为"项目内模块引用"的 import 目标做 `Path.exists()` 回查。如果引用的模块文件在项目中不存在，标记为 `broken_imports`。

**Blocked by:** None — can start in parallel with T1.

**Status:** ready-for-agent

### SPEC references
- spec-v0.4.0-file-refs.md — T2 设计要点
- handoff 盲区 3 — 项目内模块被移动/重命名后 import 静默失效

### TDD 流程

1. **先补充测试** → `tests/test_local_graph.py`
   - 正常引用（目标文件存在）
   - 断裂引用（目标文件不存在或被重命名）
   - 混合场景（部分存在 + 部分断裂）
2. **再扩展现有实现** → `scripts/extractors/local_graph.py`
3. **全量测试** → `pytest tests/ -x -q --tb=short`

### Acceptance criteria

- [ ] 对每个本地模块引用做 `Path.exists()` 回查
- [ ] 输出中新增 `broken_imports` 字段：`{"file": "src/old_module.py", "imports": ["utils"], "broken_imports": ["deleted_module"]}`
- [ ] 不破坏现有输出格式
- [ ] 不引入新的三方依赖
- [ ] 现有 76 个测试全部保持绿色

### Key files
- `E:\project\project-insight\scripts\extractors\local_graph.py` — 修改
- `E:\project\project-insight\tests\test_local_graph.py` — 补充测试
