# T3 — 补充 `env_vars.py`：补齐环境变量扫描变体

**What to build:** 当前 `env_vars.py` 只扫描 `os.environ.get()` 和 `os.getenv()`。补齐以下变体：`os.environ["KEY"]`、`environ["KEY"]`、`os.environ.get("KEY")`（不带 `os.` 前缀的 short form）、`environ.setdefault("KEY", val)`。

**Blocked by:** None — can start in parallel with T1/T2.

**Status:** ready-for-agent

### SPEC references
- spec-v0.4.0-file-refs.md — T3 设计要点
- handoff 盲区 4 — 环境变量样式不一致

### TDD 流程

1. **先补充测试** → `tests/test_env_vars.py`
   - `os.environ["KEY"]` 匹配
   - `environ["KEY"]` 匹配
   - `os.environ.get("KEY")` 已覆盖（现有测试）
   - `environ.get("KEY")` 匹配
   - `environ.setdefault("KEY", "val")` 匹配
2. **再补充实现** → `scripts/extractors/env_vars.py`，新增 `ENV_VARIANT_PATTERN` 正则或调整现有 `PYTHON_ENV_PATTERNS`
3. **全量测试** → `pytest tests/ -x -q --tb=short`

### Acceptance criteria

- [ ] `os.environ["KEY"]` 被正确提取（标记 default: None / required: true）
- [ ] `environ["KEY"]` 被正确提取
- [ ] `environ.get("KEY")` 被正确提取
- [ ] 所有现有测试保持绿色
- [ ] 提取结果和已有统一格式保持一致

### Key files
- `E:\project\project-insight\scripts\extractors\env_vars.py` — 修改
- `E:\project\project-insight\tests\test_env_vars.py` — 补充测试
