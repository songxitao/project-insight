# T4 — 代码审查遗留修复

基于 spec.md 代码审查的收尾工作。P0/P1 全部完成，本节只处理剩余低优先级问题。

---

## 依赖关系

```
T4.1 (版本号) ─ 独立
T4.2 (SKIP_DIRS 同步) ─ 独立
T4.3 (format_plain 全覆盖) ─ 独立，但内部 5 个子任务互相独立可并行
```

---

## T4.1 — pyproject.toml 版本号同步

**文件**：`pyproject.toml`

**改动**：

```toml
# 改前
version = "0.2.0"

# 改后
version = "0.3.0"
```

**验收**：`pyproject.toml` 中 `version = "0.3.0"`

---

## T4.2 — tree.py 的 SKIP_DIRS 与共享版同步

**文件**：`scripts/extractors/tree.py`

**问题**：`tree.py` 有自己的 `SKIP_DIRS`（第 19-26 行），比 `extractors/__init__.py` 多了一项 `__init__.py`。以后加新目录要改两处。

**改动**：

```python
# tree.py 第 19 行起，改前：
SKIP_DIRS = frozenset({
    '__pycache__', '.git', 'venv', '.venv', 'env',
    ...
    '.scratch', '.egg-info', 'site-packages', '__init__.py',
})

# 改后：
from . import SKIP_DIRS as _BASE_SKIP_DIRS

SKIP_DIRS = _BASE_SKIP_DIRS | {'__init__.py'}
```

删除 tree.py 内联的 19 项 frozenset 定义，改为从共享模块 import 后 union 独有项。

**注意**：`BINARY_EXTS` 和 `MAX_LINES_READ_MB` 两个常量**保留不动**——它们是 tree.py 独有的，不属于 SKIP_DIRS 范畴。

**验收**：
- `tree.SKIP_DIRS` 包含共享版所有项 + `__init__.py`
- 共享版新增跳过目录后 tree.py 自动同步
- 76 测试全绿

---

## T4.3 — format_plain() 全覆盖

**文件**：`scripts/extractors/{deps,entries,imports,paths,local_graph}.py` + `scripts/project_insight.py`

**问题**：目前 4/9 个 extractor 有 `format_plain()`，其余 5 个走 `_format_generic` 的巨型 if/elif 兜底。目标：让所有 extractor 自带 `format_plain()`，`_format_generic` 退化为纯兜底。

### T4.3a — deps.py

新增：

```python
def format_plain(data: dict) -> str:
    """格式化依赖展示"""
    lines = []
    pyproject = data.get('pyproject_deps', [])
    reqs = data.get('requirements_deps', [])
    install = data.get('install_scripts', [])

    if pyproject:
        lines.append(f"\n📦 pyproject.toml 依赖 ({len(pyproject)} 项):")
        for d in sorted(pyproject):
            lines.append(f"  • {d}")

    if reqs:
        lines.append(f"\n📜 requirements 依赖 ({len(reqs)} 项):")
        for d in sorted(reqs):
            lines.append(f"  • {d}")

    if install:
        lines.append(f"\n📜 安装脚本中的依赖:")
        for s in install:
            lines.append(f"  {s['file']}: {', '.join(s.get('packages', []))}")

    return '\n'.join(lines)
```

从 `project_insight.py` 的 `_format_generic` 中搬 `pyproject_deps` / `requirements_deps` / `install_scripts` 三个分支的逻辑。

### T4.3b — entries.py

新增：

```python
def format_plain(data: dict) -> str:
    """格式化入口点与 API 端点展示"""
    lines = []
    eps = data.get('entry_points', [])
    apis = data.get('api_endpoints', [])

    if eps:
        lines.append(f"\n🚪 入口点 ({len(eps)} 个):")
        for ep in eps:
            lines.append(f"  [{ep['type']}] {ep['file']}:{ep['line']}")
            lines.append(f"    └─ {ep['context'][:80]}...")

    if apis:
        lines.append(f"\n🌐 API 端点 ({len(apis)} 个):")
        for ep in apis:
            lines.append(f"  {ep['route']}  ({ep['file']}:{ep['line']})")

    return '\n'.join(lines)
```

从 `_format_generic` 搬 `entry_points` / `api_endpoints` 两个分支。

### T4.3c — imports.py

新增：

```python
def format_plain(data: dict) -> str:
    """格式化 import 展示"""
    source_imports = data.get('source_imports', {})
    if not source_imports:
        return ''
    lines = [f"\n🔗 源码 import ({len(source_imports)} 个文件):"]
    for f, imps in sorted(source_imports.items()):
        lines.append(f"  {f} → {', '.join(sorted(imps))}")
    return '\n'.join(lines)
```

从 `_format_generic` 搬 `source_imports` 分支。

### T4.3d — paths.py

新增：

```python
def format_plain(data: dict) -> str:
    """格式化本地路径展示"""
    local_paths = data.get('local_paths', [])
    if not local_paths:
        return ''
    lines = ["\n⚠️  本地路径硬编码:"]
    for s in local_paths:
        for p in s['paths']:
            lines.append(f"  {s['file']} → {p}")
    return '\n'.join(lines)
```

从 `_format_generic` 搬 `local_paths` 分支。

### T4.3e — local_graph.py

新增：

```python
def format_plain(data: dict) -> str:
    """格式化本地依赖图展示"""
    graph = data.get('local_dep_graph', {})
    if not graph:
        return ''
    lines = [f"\n🔀 本地模块依赖图 ({len(graph)} 条):"]
    for f, refs in sorted(graph.items()):
        lines.append(f"  {f} → {', '.join(refs)}")
    return '\n'.join(lines)
```

从 `_format_generic` 搬 `local_dep_graph` 分支。

### T4.3f — 清理 _format_generic

**文件**：`scripts/project_insight.py`

5 个 extractor 实现 `format_plain()` 后，`_format_generic` 中对应的 5 个 if/elif 分支不再被调用，可以删除。保留 `project_tree` 分支作为 `tree` 模块的特殊兜底。

删除的分支 key：`pyproject_deps`、`requirements_deps`、`install_scripts`、`source_imports`、`local_paths`、`entry_points`、`api_endpoints`、`local_dep_graph`

保留的分支：`project_tree`（tree 已有 `format_plain()` 走分发器，不移除，保留为 `_format_generic` 内部工具）

**验收**：
- 所有 9 个 extractor 均实现 `format_plain()`
- `_format_generic` 仅剩 `project_tree` 一个特殊分支
- `python scripts/project_insight.py . --format plain` 输出与改造前一致
- 76 测试全绿

---

## 执行顺序

1. T4.1（版本号）— 1 行改动，先做
2. T4.2（SKIP_DIRS 同步）— 独立
3. T4.3a~T4.3e（format_plain 实现）— 5 个 extractor 独立，可并行
4. T4.3f（清理 _format_generic）— 依赖 T4.3a~T4.3e 全部完成

---

## 额外：entries.py API_PATTERN 正则优化（可选）

**文件**：`scripts/extractors/entries.py` 第 25 行

**问题**：`\.\s*` 中 `\s*` 允许点号后任意空格（`@app .get` 也能匹配），虽然实际不影响正常匹配（零空格也走 `\s*`），但不够精确。

**改动**（可选执行）：

```python
# 改前
API_PATTERN = re.compile(
    r"@(?:app|router|api)\.\s*(?:get|post|put|delete|patch|route|websocket)\s*\(\s*['\"](.+?)['\"]"
)

# 改后
API_PATTERN = re.compile(
    r"@(?:app|router|api)\.(?:get|post|put|delete|patch|route|websocket)\s*\(\s*['\"](.+?)['\"]"
)
```

**注意**：此改动是低风险的精确化，属于锦上添花，不阻塞 T4 主线。
