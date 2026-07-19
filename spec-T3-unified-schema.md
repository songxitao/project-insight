# T3 Spec: 统一输出 Schema（候选 B）

## 目标

建立 extractor 的统一输出协议，让 `_print_plain` 从 22 个 if/elif 分支 + 4 个特例格式化函数，简化为一个通用分发循环。每个 extractor 可选提供 `format_plain()` 方法控制自己的展示逻辑。

## 核心设计

### 接口：`format_plain(data: dict) -> str`

每个 extractor 模块可**选择性**定义 `format_plain(data)` 函数：
- 接收该模块的 data dict（即 `run()` 返回的 dict）
- 返回格式化后的纯文本字符串（含换行）
- 可以不定义 — 未定义时走通用格式化

注册表中存储模块引用而非仅 `run()`：
```python
# extractors/__init__.py
REGISTRY: dict[str, dict] = {}  # {name: {'run': func, 'mod': module}}
...
if hasattr(mod, 'run'):
    REGISTRY[name] = {'run': mod.run, 'mod': mod}
```

### `_print_plain` 改造

从硬编码分支改为：
```python
def _print_plain(result: dict):
    for module_name in sorted(result.keys()):
        data = result[module_name]
        if isinstance(data, dict) and 'error' in data:
            print(f"\n⚠️  {module_name}: 错误 — {data['error']}")
            continue
        entry = REGISTRY.get(module_name)
        if entry and hasattr(entry['mod'], 'format_plain'):
            print(entry['mod'].format_plain(data))
        else:
            print(_format_generic(module_name, data))
```

### 通用格式化兜底

`_format_generic(module_name, data) -> str` 取代当前的 print 语句，返回字符串而非直接 print。处理所有已知 key 的格式化，确保未实现 `format_plain()` 的模块仍能正常展示。

## 各 extractor 的 format_plain() 规划

| Extractor | 当前格式化方式 | format_plain 计划 |
|-----------|--------------|-----------------|
| `deps` | `_format_generic` 内三个 key | 可选实现，也可不写走通用 |
| `entries` | `_format_generic` 下 entry_points/api_endpoints | 可选 |
| `env_vars` | `_format_env_vars` 特例 | **强烈建议实现** — 逻辑较复杂 |
| `imports` | `_format_generic` 下 source_imports | 可选 |
| `local_graph` | `_format_generic` 下 local_dep_graph | 可选 |
| `model_refs` | `_format_model_refs` 特例 | **强烈建议实现** |
| `paths` | `_format_generic` 下 local_paths | 可选 |
| `tree` | `_format_tree` 特例 | **强烈建议实现** — 递归树打印 |
| `urls` | `_format_urls` 特例 | **强烈建议实现** |

**最少实现**：`env_vars`、`model_refs`、`tree`、`urls` 四个模块实现 `format_plain()`，其余走通用兜底。

## 改动清单

### 文件 1：`extractors/__init__.py`

REGISTRY 从 `{name: run_func}` 改为 `{name: {'run': run_func, 'mod': module_ref}}`。

### 文件 2：`project_insight.py`

- `_print_plain` 改造为通用分发器
- 删除 `_format_env_vars`、`_format_model_refs`、`_format_urls` 三个函数（下沉到各自模块）
- 保留 `_print_tree` 作为 `_format_generic` 内部调用的工具函数
- 保留 `_format_generic` 作为兜底通用格式化（返回 str 而非直接 print）
- `main()` 中的异常处理 `result[module_name] = {'error': str(e)}` 保持不变

### 文件 3-6：4 个 extractor 实现 format_plain()

- `env_vars.py` — 新增 `format_plain(data: dict) -> str`
- `model_refs.py` — 新增 `format_plain(data: dict) -> str`
- `tree.py` — 新增 `format_plain(data: dict) -> str`
- `urls.py` — 新增 `format_plain(data: dict) -> str`

### 其余 5 个 extractor

不修改，走 `_format_generic` 兜底。

## 验收标准

1. **`python scripts/project_insight.py . --format plain` 输出与 T1 改造后一致**（无回归）
2. `REGISTRY` 结构改为 `{name: {'run': ..., 'mod': ...}}`
3. 4 个 module 实现 `format_plain()` 后，`_print_plain` 中不再出现 `_format_env_vars`、`_format_model_refs`、`_format_urls` 调用
4. `_format_generic` 改为返回 str，不再直接 print
5. 76 个 pytest 全绿
