# T5 — 更新 SKILL_REFERENCE.md + README

**What to build:** 更新项目文档，记录新增的 `file_refs` 模块和 `--strict` CLI 参数。

**Blocked by:** **T1**（file_refs 需先就绪才有内容可写）、**T4**（需确认 --strict 的最终行为）

**Status:** blocked-by-T1,T4

### SPEC references
- spec-v0.4.0-file-refs.md — 新增模块清单

### Tasks

1. **更新 `docs/SKILL_REFERENCE.md`**
   - 在模块一览表新增 `file_refs` 行
   - 新增 `file_refs` 模块的详细说明章节
   - 更新 CLI 用法示例（含 `--strict`）
2. **更新 `README.md`**
   - 模块一览表新增 `file_refs`
   - 进阶调优章节新增 `--strict` 说明

### Acceptance criteria

- [ ] `SKILL_REFERENCE.md` 包含 `file_refs` 模块文档
- [ ] `SKILL_REFERENCE.md` CLI 示例包含 `--strict`
- [ ] `README.md` 模块一览表包含 `file_refs`
- [ ] 文档中所有示例路径指向真实存在的文件

### Key files
- `E:\project\project-insight\docs\SKILL_REFERENCE.md` — 更新
- `E:\project\project-insight\README.md` — 更新
