# T1 Tickets — 共享基础设施层

## 依赖关系

```
T1.1 (__init__.py 基础设施)
  └→  T1.2 (project_insight.py 入口改造)
  └→  T1.3 ~ T1.10 (各 extractor 改造) — 互相独立，可并行
```

T1.1 必须先完成，因为所有后续 ticket 都依赖 `__init__.py` 中定义的新接口。
T1.3~T1.10 彼此无依赖，可并行执行。

---

## T1.1 — 构建 extractors/__init__.py 基础设施

**文件**：`scripts/extractors/__init__.py`

**内容**：
- `SKIP_DIRS` frozenset（见 spec）
- `should_skip(rel_path: Path) -> bool`
- `iter_project_files(root: Path, extensions=('.py',)) -> Iterator[Path]`
- `safe_read(filepath: Path | str, encoding='utf-8') -> str`
- `REGISTRY` 自动注册（`pkgutil.iter_modules` + `importlib.import_module`）

**验收**：
- `from extractors import REGISTRY, should_skip, iter_project_files, safe_read` 不报错
- `REGISTRY` 包含除 `__init__` 外的所有 extractor 名称 → `run()` 函数
- 测试：在 `extractors/` 下新建一个含 `run()` 的 .py 文件，REGISTRY 自动包含它

---

## T1.2 — 改造 project_insight.py 入口

**文件**：`scripts/project_insight.py`

**改动**：
1. 删除第 23-78 行手写 try/except ×9
2. 改为 `from extractors import REGISTRY`
3. `ALL_MODULES = sorted(REGISTRY.keys())`
4. 输出循环从 `result.update(module_result)` 改为 `result[module_name] = runner(str(root_dir))`
5. 改造 `_print_plain` 函数：从 22 个 if/elif 分支改为按 `(module_name, inner_data)` 两级结构遍历

**关键**：`_print_plain` 的改造不能破坏任何已有输出格式。每个模块的数据现在在 `result[module_name]` 下，模块内部的 key 按原有逻辑格式化。tree 的递归打印作为特例保留。

**验收**：
- `python scripts/project_insight.py . --format plain` 输出与改造前一致
- `python scripts/project_insight.py . --format json` 输出结构从扁平 key 变为 `{module_name: {...}}` 嵌套
- `python scripts/project_insight.py . --format json` 输出中用 `"deps": {...}`、`"tree": {"project_tree": ...}` 等模块名作为顶层 key

---

## T1.3 — 改造 deps.py

**文件**：`scripts/extractors/deps.py`

**改动**：
1. 删除 `skip_dir()` 函数（第 74-80 行）
2. 安装脚本遍历：将第 113-129 行的 `root.rglob('*')` + skip set 改为 `iter_project_files(root, extensions=('.bat', '.sh', '.ps1', ''))` + 自己判断 `is_script_file()`（不含扩展名时用文件名判断，如 Dockerfile）
3. 原有额外逻辑保留：requirements 候选列表、`scan_pyproject()`、`scan_requirements_txt()`、`scan_install_commands()`、`is_script_file()`
4. **不修** group(0)→group(1) bug（那是 T2 的事）

**验收**：
- `run()` 返回结构不变：`pyproject_deps`、`requirements_deps`、`install_scripts`
- 对已知项目的输出值与改造前一致

---

## T1.4 — 改造 entries.py

**文件**：`scripts/extractors/entries.py`

**改动**：
1. 遍历第 57-66 行：删除 inline skip set，改为 `for f_rel in iter_project_files(root, extensions=('.py',))`
2. `_read_snippet()` 接收绝对路径：`safe_read(root / rel_path)`
3. `f.relative_to(root)` → 直接使用 `rel_path`
4. 保留 `_read_snippet()`、`_get_context_lines()`、正则模式

**验收**：
- `run()` 返回 `entry_points` + `api_endpoints`
- 输出值与改造前一致

---

## T1.5 — 改造 env_vars.py

**文件**：`scripts/extractors/env_vars.py`

**改动**：
1. 删除 `_is_skip_dirs()` 函数（第 113-119 行）
2. Python 文件遍历（第 132-133 行）：改为 `for f_rel in iter_project_files(root, extensions=('.py',))`
3. **自然地修复了变量遮蔽 bug**（原第 119 行 `for p in p.parents`）
4. `.env` 和 `docker-compose.yml` 文件扫描保留原样（不走 iter_project_files，因为它们是根目录特定文件）
5. 保留所有提取函数：`_extract_from_python()`、`_extract_from_env()`、`_extract_from_docker_compose()`

**验收**：
- `run()` 返回 `env_vars` + `env_vars_summary`
- 输出值与改造前一致
- 变量遮蔽 bug 不复存在

---

## T1.6 — 改造 imports.py

**文件**：`scripts/extractors/imports.py`

**改动**：
1. 遍历第 58-67 行：删除 inline skip set，改为 `for f_rel in iter_project_files(root, extensions=('.py',))`
2. `f.relative_to(root)` → 直接使用 `rel_path`
3. 保留 `scan_imports()`

**验收**：
- `run()` 返回 `source_imports`
- 输出值与改造前一致

---

## T1.7 — 改造 paths.py

**文件**：`scripts/extractors/paths.py`

**改动**：
1. 遍历第 30-39 行：删除 inline skip set，改为 `for f_rel in iter_project_files(root, extensions=('.py', '.bat', '.sh', '.ps1', ''))` + 自己判断 Dockerfile
2. `f.relative_to(root)` → 直接使用 `rel_path`
3. 保留 `scan_local_paths()`

**验收**：
- `run()` 返回 `local_paths`
- 输出值与改造前一致

---

## T1.8 — 改造 urls.py

**文件**：`scripts/extractors/urls.py`

**改动**：
1. 删除 `_is_skip_dirs()` 函数（第 68-74 行）
2. 遍历第 85-89 行：改为 `for f_rel in iter_project_files(root, extensions=('.py', '.bat', '.sh', '.ps1', '.yaml', '.yml', '.json', '.toml', '.cfg', '.ini', '.env', '.conf'))`
3. `f.relative_to(root)` → 直接使用 `rel_path`

**验收**：
- `run()` 返回 `hardcoded_urls` + `hardcoded_urls_summary`
- 输出值与改造前一致

---

## T1.9 — 改造 model_refs.py

**文件**：`scripts/extractors/model_refs.py`

**改动**：
1. 删除 `_is_skip_dirs()` 函数（第 55-61 行）
2. 遍历第 72-76 行：改为 `for f_rel in iter_project_files(root, extensions=('.py', '.bat', '.sh', '.ps1', '.yaml', '.yml', '.json'))`
3. `f.relative_to(root)` → 直接使用 `rel_path`

**验收**：
- `run()` 返回 `model_refs` + `model_refs_summary`
- 输出值与改造前一致

---

## T1.10 — 改造 local_graph.py

**文件**：`scripts/extractors/local_graph.py`

**改动**：
1. `_collect_local_modules()` 中遍历第 23-32 行：删除 inline skip set，改为 `for f_rel in iter_project_files(root, extensions=('.py',))`
2. `_get_source_imports()` 中遍历第 77-86 行：删除 inline skip set，改为 `for f_rel in iter_project_files(root, extensions=('.py',))`
3. `f.relative_to(root)` → 直接使用 `rel_path`

**验收**：
- `_collect_local_modules()` 返回模块字典（去掉 .py 后缀、注册变体）
- `_get_source_imports()` 返回文件和 import 映射
- `run()` 返回 `local_dep_graph`
- 输出值与改造前一致

---

## T1.11 — tree.py 检查

**文件**：`scripts/extractors/tree.py`

**改动**：**不需要改代码**，只需确认：
- `tree.py` 的递归 `_build_tree()` 不走 rglob，不依赖 `iter_project_files`
- 自动注册后 `REGISTRY["tree"] = tree.run` 正常
- 命名空间下 `result["tree"] = {"project_tree": ...}` 多一层嵌套，`_print_plain` 要适配

**验收**：
- tree 模块在命名空间下的输出为 `result["tree"]["project_tree"]`
- 无功能退化
