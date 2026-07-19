# T3 Tickets — 统一输出 Schema

## 依赖关系

```
T3.1 (REGISTRY 结构改造) → T3.2 (_print_plain 分发器)
                                └→ T3.3~T3.6 (format_plain 实现) — 互相独立，可并行
```

T3.1 和 T3.2 必须按顺序先后执行。T3.3~T3.6 在 T3.2 完成后可并行。

---

## T3.1 — REGISTRY 结构改为 {name: {'run': ..., 'mod': ...}}

**文件**：`scripts/extractors/__init__.py`

**改动**：
```python
# 改前
REGISTRY: dict[str, callable] = {}
for _finder, name, _ispkg in pkgutil.iter_modules(__path__):
    mod = importlib.import_module(f".{name}", __package__)
    if hasattr(mod, 'run'):
        REGISTRY[name] = mod.run

# 改后
REGISTRY: dict[str, dict] = {}
for _finder, name, _ispkg in pkgutil.iter_modules(__path__):
    mod = importlib.import_module(f".{name}", __package__)
    if hasattr(mod, 'run'):
        REGISTRY[name] = {'run': mod.run, 'mod': mod}
```

**验收**：
- `REGISTRY['deps']` → `{'run': <function>, 'mod': <module>}`
- 所有 9 个模块都正确注册

---

## T3.2 — 改造 _print_plain 为通用分发器

**文件**：`scripts/project_insight.py`

**改动**：
1. 从 `from extractors import REGISTRY` 改为 `from extractors import REGISTRY`
2. `main()` 中 `runner = REGISTRY.get(module_name)` → `runner = REGISTRY.get(module_name, {}).get('run')`
3. `_print_plain` 改为通用分发器：
   - 遍历 `result[module_name]`
   - 如果 `REGISTRY[module_name]['mod']` 有 `format_plain()` → 调用
   - 否则 → `_format_generic(module_name, data)`
4. 删除 `_format_env_vars`、`_format_model_refs`、`_format_urls`
5. `_format_generic` 改为返回 str 而非直接 print
6. 保留 `_print_tree` 作为 `_format_generic` 内部工具

**验收**：
- `python scripts/project_insight.py . --format plain` 输出与 T1 后一致
- `_print_plain` 不再包含 `_format_env_vars`、`_format_model_refs`、`_format_urls` 调用
- 76 个测试全绿（需要同时适配现有测试）

---

## T3.3 — env_vars.py 实现 format_plain()

**文件**：`scripts/extractors/env_vars.py`

**新增函数**：
```python
def format_plain(data: dict) -> str:
    """格式化环境变量展示"""
    lines = []
    grouped = data.get('env_vars', {})
    summary = data.get('env_vars_summary', [])
    # ... 格式化逻辑，append 到 lines
    return '\n'.join(lines)
```

内容从当前 `_format_env_vars` 搬过来，将 `print()` 改为 `lines.append()`。

**验收**：plain 输出中 env_vars 部分与改造前一致。

---

## T3.4 — model_refs.py 实现 format_plain()

**文件**：`scripts/extractors/model_refs.py`

**新增函数**：
```python
def format_plain(data: dict) -> str:
    lines = ['\n🤖 模型引用:']
    # ... 从当前 _format_model_refs 搬过来
    return '\n'.join(lines)
```

**验收**：plain 输出中 model_refs 部分与改造前一致。

---

## T3.5 — tree.py 实现 format_plain()

**文件**：`scripts/extractors/tree.py`

**新增函数**：
```python
def format_plain(data: dict) -> str:
    lines = ['\n🌳 项目骨架树:']
    tree_data = data.get('project_tree')
    if tree_data:
        _append_tree(tree_data, lines, indent=2)
    return '\n'.join(lines)
```

需要从 `project_insight.py` 把 `_print_tree` 的逻辑搬过来（递归），或者让 `_print_tree` 接收一个 `lines` 参数。更干净的做法是 tree.py 内部实现递归格式化。

**注意**：`_print_tree` 目前是 `project_insight.py` 的模块级函数，T3.2 中还保留了它。如果 tree.py 自己实现了树格式化，`_print_tree` 仅在 `_format_generic` 中作为兜底调用。

**验收**：plain 输出中 tree 部分与改造前一致。

---

## T3.6 — urls.py 实现 format_plain()

**文件**：`scripts/extractors/urls.py`

**新增函数**：
```python
def format_plain(data: dict) -> str:
    lines = []
    refs = data.get('hardcoded_urls', [])
    # ... 从当前 _format_urls 搬过来
    return '\n'.join(lines)
```

**验收**：plain 输出中 urls 部分与改造前一致。
