# T6 — 金样本集成测试（端到端快照）

**What to build:** 选择 1 个真实开源小项目作为金样本，运行 `project-insight --format json` 输出快照，断言关键字段存在。防正则改动引入静默回归。

**Blocked by:** **T1**、**T2**、**T3** — 需等新功能就绪后才能做端到端快照。

**Status:** blocked-by-T1,T2,T3

### SPEC references
- spec-v0.4.0-file-refs.md — 金样本集成测试

### Tasks

1. **选择金样本**：选一个已知的极小 Python 开源项目（如 `project-insight` 自身，或一个已知文件结构简单的项目）
2. **编写测试** → `tests/test_project_insight.py` 补充
   - 对金样本项目运行 `project-insight --format json`
   - 断言输出包含 `deps`/`imports`/`tree`/`entries`/`env_vars`/`model_refs`/`paths`/`urls`/`local_graph`/`file_refs` 所有模块
   - 断言各模块的 key 结构符合预期
3. **实现 `format_plain()` 覆盖验证**：每个新模块的 plain 输出不抛出异常

### Acceptance criteria

- [ ] 金样本端到端运行成功
- [ ] JSON 输出包含全部 10 个模块的命名空间
- [ ] 各模块输出字段结构符合 spec 定义的 schema
- [ ] `--format plain` 对所有模块无异常输出

### Key files
- `E:\project\project-insight\tests\test_project_insight.py` — 补充
- 金样本项目目录（可选用 `tests/fixtures/` 或一个已知的本地项目）
