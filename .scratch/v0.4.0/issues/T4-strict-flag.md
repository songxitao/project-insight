# T4 — 新增 `--strict` 标志 + 断裂引用汇总

**What to build:** 在 CLI 入口 `project_insight.py` 新增 `--strict` / `-s` 标志。运行后检查所有模块输出中是否存在 `exists: false` / `broken_imports` 等断裂标记。若有则 exit 1，否则 exit 0。默认（无 `--strict`）→ warn 输出，exit 0。

**Blocked by:** **T1** — file_refs 的输出是 strict 模式判断的数据源。

**Status:** blocked-by-T1

### SPEC references
- spec-v0.4.0-file-refs.md — T4 设计要点
- handoff 盲区 1 — CI 场景需要 exit code 来 fail pipeline

### TDD 流程

1. **先补充测试** → `tests/test_project_insight.py`
   - 默认模式（有断裂引用）→ exit 0，stderr 有 warn
   - `--strict` 模式（有断裂引用）→ exit 1
   - `--strict` 模式（无断裂引用）→ exit 0
2. **再修改实现** → `scripts/project_insight.py`
   - 新增 `--strict` argparse 参数
   - `main()` 运行完毕后扫描汇总结果
3. **全量测试** → `pytest tests/ -x -q --tb=short`

### Acceptance criteria

- [ ] `--strict` / `-s` CLI 参数可用
- [ ] 默认模式：断裂引用 → stderr 输出 `[WARN]`，exit 0
- [ ] `--strict` + 断裂引用 → exit 1
- [ ] `--strict` + 无断裂引用 → exit 0
- [ ] 不影响 `--format json` 输出
- [ ] 不影响 `--modules` 参数行为
- [ ] 现有 76 个测试全部保持绿色

### Key files
- `E:\project\project-insight\scripts\project_insight.py` — 修改
- `E:\project\project-insight\tests\test_project_insight.py` — 补充测试
