# T1 — 新增 `file_refs.py`：相对路径引用扫描 + 存在性校验

**What to build:** 新增 `scripts/extractors/file_refs.py` 模块，扫描 `.py` 文件中 `Path("")`/`open("")`/subprocess 脚本引用等相对文件路径，并检查目标文件是否存在。同时新增对应的测试文件。

**Blocked by:** None — can start immediately.

**Status:** ready-for-agent

### SPEC references
- spec-v0.4.0-file-refs.md — T1 设计要点
- handoff 盲区 1 — 正则草稿 `REL_PATH_PATTERN` / `SCRIPT_REF_PATTERN`
- handoff 盲区 3 — file_refs 负责"文件系统级引用"，local_graph 负责"模块级引用"

### TDD 流程（严格遵循）

1. **先写测试** → `tests/test_file_refs.py`，覆盖以下场景：
   - `Path("app_control.py")` 匹配且文件存在 → `exists: true`
   - `Path("missing.py")` 匹配但文件不存在 → `exists: false`
   - `open("data.json")` 匹配
   - `subprocess.Popen(["python", "script.py"])` 匹配
   - 裸字符串无扩展名 → 过滤不报
   - 空项目 → 空结果
   - 跳过目录不扫描
2. **再写实现** → `scripts/extractors/file_refs.py`
3. **运行全量测试** → `pytest tests/ -x -q --tb=short`
4. **代码审查** → Standards + Spec 双轴

### Acceptance criteria

- [ ] `Path("xxx.py")` 被正确提取（含文件存在性标记）
- [ ] `open("xxx.json")` 被正确提取
- [ ] `subprocess` 中的脚本引用被正确提取
- [ ] 无扩展名的裸字符串被过滤
- [ ] 跳过目录（`__pycache__`/`.git`/`venv` 等）不扫描
- [ ] 输出格式规范：`{"file_refs": [{"file":..., "line":..., "ref":..., "type":..., "exists":...}]}`
- [ ] 实现 `format_plain()` 纯文本输出
- [ ] 现有 76 个测试全部保持绿色

### Key files
- `E:\project\project-insight\scripts\extractors\file_refs.py` — 新建
- `E:\project\project-insight\tests\test_file_refs.py` — 新建
- `E:\project\project-insight\scripts\extractors\__init__.py` — pkgutil 自动注册，无需修改
