好的尖子，以下是基于 `/code-review`（Standards 轴）和 `/improve-codebase-architecture`（Deepening 轴）两个 skill 的完整审查结果。直接复制给 DeepSeek 用。

---

## 一、Standards 轴：代码异味与规范问题

### 1. Duplicated Code（重复代码）—— 最严重的问题

`skip_dirs` 集合在 **7 个文件中重复定义了 7 次**，每次都是手写的内联 set literal：

- `deps.py` 第 75-79 行（`skip_dir()` 函数内）
- `deps.py` 第 116-120 行（`run()` 函数内，同一个文件写了两遍！）
- `entries.py` 第 60-65 行
- `imports.py` 第 61-66 行
- `local_graph.py` 第 26-31 行
- `env_vars.py` 第 114-118 行
- `urls.py` 第 69-73 行
- `model_refs.py` 第 56-60 行
- `paths.py` 第 33-38 行

而 `tree.py` 用了 `frozenset` 模块级常量（`SKIP_DIRS`），是唯一做对了的。

**修复**：在 `extractors/__init__.py` 中定义一次 `SKIP_DIRS` 常量和一个共享的 `should_skip(path)` 工具函数，所有模块统一 import 使用。

### 2. Duplicated Code（重复代码）—— 目录遍历逻辑

每个 extractor 的 `run()` 函数里都有几乎相同的遍历模板：

```python
for f in sorted(root.rglob('*.py')):
    if not f.is_file():
        continue
    if any(p.name in {那个重复集合} for p in f.parents):
        continue
```

这段逻辑出现了至少 6 次。

**修复**：在 `extractors/__init__.py` 中提供一个共享的 `iter_project_files(root, extensions=('.py',))` 生成器，所有 extractor 直接 `for f in iter_project_files(root):`。

### 3. Shotgun Surgery（散弹手术）

如果你想新增一个需要跳过的目录（比如 `.tox`），你需要同时改 **7+ 个文件**中的 skip set。这是经典的 shotgun surgery：一个逻辑变更需要散弹式修改多处。上面的统一 `SKIP_DIRS` 方案同时解决此问题。

### 4. Duplicated Code —— `_is_skip_dirs` 函数写了 3 遍

`env_vars.py`、`urls.py`、`model_refs.py` 各有一个 `_is_skip_dirs()` 函数，逻辑完全相同。而 `deps.py` 有个 `skip_dir()` 函数签名不同但干的事一样。合并。

### 5. 注册表手写 try/except ×9

`project_insight.py` 第 23-78 行，9 个 extractor 模块逐个手写 `try: from extractors import xxx; REGISTRY[name] = xxx.run` + `except`。新增模块要手动加代码。

**修复**：用 `pkgutil.iter_modules` + `importlib.import_module` 自动发现。`extractors/__init__.py` 改成：

```python
import importlib, pkgutil
REGISTRY = {}
for _, name, _ in pkgutil.iter_modules(__path__):
    try:
        mod = importlib.import_module(f".{name}", __package__)
        if hasattr(mod, 'run'):
            REGISTRY[name] = mod.run
    except Exception as e:
        import sys
        print(f"[WARN] {name} 模块加载失败: {e}", file=sys.stderr)
```

主入口直接 `from extractors import REGISTRY`。

### 6. `result.update()` 有 key 覆盖风险

`project_insight.py` 第 134 行 `result.update(module_result)`——如果两个 extractor 返回同名 key，后者静默覆盖前者，无任何警告。

**修复**：改成按模块名做命名空间：`result[module_name] = runner(root_dir)`，或者至少加覆盖检测。

### 7. `_is_skip_dirs` 有变量遮蔽 bug

`env_vars.py` 第 113-119 行：

```python
def _is_skip_dirs(p: Path) -> bool:
    skip = {...}
    return any(p.name in skip for p in p.parents)
```

生成器表达式中的 `for p in p.parents` 的循环变量 `p` 遮蔽了函数参数 `p`。`urls.py` 和 `model_refs.py` 用的是 `for part in p.parents`，没有这个问题。`env_vars.py` 这里实际上是个 bug——函数参数被覆盖后，`p.parents` 的行为取决于最后一次迭代的 `p`。

**修复**：改成 `for part in p.parents`。

### 8. `scan_requirements_txt` 返回值不对

`deps.py` 第 50 行：`deps.append(m.group(0).strip())`——用的是 `group(0)`（整个匹配），而不是 `group(1)`（包名部分）。这意味着结果可能包含版本号后面的逗号分号等垃圾字符。应该用 `group(1)`。

### 9. requirements 文件只取第一个就 break

`deps.py` 第 106-110 行，`req_candidates` 列表里有 6 个变体，但找到第一个就 `break` 了。如果项目同时有 `requirements.txt` 和 `requirements-dev.txt`，后者会被忽略。

**修复**：改成收集所有找到的 requirements 文件，按文件名分别输出（像 `install_scripts` 那样做 list）。

### 10. `entries.py` 的 API_PATTERN 正则有误

第 23 行：`@(?:app|router|api)\\.\\s*(?:get|post|...)`——注意 `\\.\\s*`，点号后面跟了 `\\s*`。实际 FastAPI 写法是 `@app.get("/path")`，点号和方法名之间不会有空格。更关键的是，这个正则要求 `@app.` 后面有空格才匹配，但真正的问题是它**不匹配** `@router.get` 这种正常写法，因为 `\\.` 后面的 `\\s*` 实际上会让它匹配 `@app. get`（点后空格）这种不存在的写法。需要把 `\\.\\s*` 改成 `\\.`。

### 11. Mysterious Name

- `_get_context_lines` 的参数 `max_lines` 实际含义是 `total_lines`（行数上限），名字有误导。
- `_read_snippet` 这个函数名没有暗示"读头尾、跳中间"的行为。建议改成 `_read_head_tail`。

### 12. 没有类型标注的返回值

所有 `run()` 函数返回 `dict`，但没有用 `TypedDict` 或至少在 docstring 中描述返回 dict 的 key schema。对于一个面向 AI agent 消费的工具，输出 schema 文档至关重要。

---

## 二、Architecture 轴：Deepening 机会

### 候选 A：提取共享基础设施层（Strong 推荐）

**涉及文件**：所有 9 个 extractor + `project_insight.py` + `extractors/__init__.py`

**问题**：当前每个 extractor 都是独立的浅模块——各自内部重新定义文件遍历逻辑、skip 列表、文件读取错误处理。模块的"接口"（`run(root_dir) -> dict`）很小很好，但**实现中 80% 的代码在做相同的脚手架工作**而不是做各自的提取逻辑。

**方案**：在 `extractors/__init__.py` 中建立共享基础设施：

```python
# extractors/__init__.py
from pathlib import Path
import importlib, pkgutil

SKIP_DIRS = frozenset({
    '__pycache__', '.git', 'venv', '.venv', 'env',
    'node_modules', 'build', 'dist', '.pytest_cache',
    '.ruff_cache', '.workbuddy', 'output', 'outputs',
    'testset', 'model', 'models', 'checkpoints',
    '.pilot_venv', '.superpowers', '.agents', '.claude',
    '.scratch', '.egg-info', 'site-packages',
})

def should_skip(path: Path) -> bool:
    """检查路径的任意父目录是否在跳过列表中"""
    return any(part in SKIP_DIRS for part in path.parts)

def iter_project_files(root: Path, extensions: tuple = ('.py',)) -> Iterator[Path]:
    """遍历项目文件，自动跳过非代码目录"""
    for f in sorted(root.rglob('*')):
        if not f.is_file():
            continue
        if should_skip(f.relative_to(root)):
            continue
        if extensions and f.suffix.lower() not in extensions:
            continue
        yield f

def safe_read(filepath: Path, encoding='utf-8') -> str:
    """安全读取文件内容，出错返回空字符串"""
    try:
        return filepath.read_text(encoding=encoding, errors='replace')
    except Exception:
        return ''

# 自动注册
REGISTRY = {}
for _, name, _ in pkgutil.iter_modules(__path__):
    try:
        mod = importlib.import_module(f".{name}", __package__)
        if hasattr(mod, 'run'):
            REGISTRY[name] = mod.run
    except Exception:
        pass
```

**收益**：
- 删除 7 处重复的 skip set（约 50 行重复代码）
- 删除 6+ 处重复的遍历模板（约 40 行重复代码）
- 新增 extractor 只需写提取逻辑，不需要写任何遍历/过滤/注册代码
- 新增 skip 目录改一处生效全局

### 候选 B：统一输出 schema（Worth exploring）

**涉及文件**：所有 extractor + `project_insight.py`

**问题**：每个 extractor 的返回 dict 的 key 命名风格不统一——有的用 `_summary` 后缀（`env_vars_summary`、`model_refs_summary`、`hardcoded_urls_summary`），有的没有。有的返回 1 个 key（`tree` 返回 `project_tree`），有的返回 2 个（`urls` 返回 `hardcoded_urls` + `hardcoded_urls_summary`），有的返回 3 个（`deps` 返回 `pyproject_deps` + `requirements_deps` + `install_scripts`）。主入口的 `_print_plain` 必须逐个 hardcode 每种 key 的打印逻辑（22 个 if/elif 分支）。

**方案**：定义统一的输出协议：

```python
class ExtractorResult:
    """每个 extractor 返回的标准化结果"""
    module: str          # 模块名
    data: dict           # 主数据
    summary: dict | None # 汇总数据（可选）
    
    def to_dict(self) -> dict:
        result = {self.module: self.data}
        if self.summary:
            result[f"{self.module}_summary"] = self.summary
        return result
```

同时让 `_print_plain` 支持每个 extractor 自带 `format_plain()` 方法——把展示逻辑下沉到模块内部，主入口只做循环调用。

### 候选 C：支持非 Python 项目的扩展点（Speculative）

**问题**：当前所有 extractor 都 hardcode 了 `.py` 扩展名和 Python 特有的模式（`pyproject.toml`、`import`、`os.environ`）。如果想支持 Node.js（`package.json`、`require()`、`process.env`）或 Go（`go.mod`），每个 extractor 都要改。

**方案**：这个暂时不需要做，但 README 应该明确标注"仅限 Python 项目"。如果未来真要扩展，上面候选 A 的基础设施层就是天然的扩展点——每种语言一组 extractor，共享遍历基础设施。

---

## 三、文档与项目配置问题

### 1. SKILL_REFERENCE.md 严重过期

`docs/SKILL_REFERENCE.md` 还在引用 `scripts/qc_extract_deps.py`（这个文件不存在），还在说"四类正则扫描模式"（现在是 9 个模块），用法示例是错的。必须重写，与 README 对齐到 v2 架构。

### 2. README 缺少关键信息

- 没有说"仅限 Python 项目"
- 没有输出示例（一个 `--format json` 的实际输出 example）
- 没有 `--modules` 参数的用法说明
- 没有安装方式说明

### 3. 缺少 CLI 入口点

`pyproject.toml` 没有 `[project.scripts]`，用户 `pip install` 后无法通过命令行直接运行。建议加：

```toml
[project.scripts]
project-insight = "project_insight:main"
```

但这需要先把包结构从 `scripts/` 调整为标准 Python 包布局。

### 4. `project_insight_v1.py` 应该删除

v1 文件仍留在 `scripts/` 下，且没有被任何代码引用。既然已经有 v2 架构和 CHANGELOG 记录，v1 应该删除（Git 历史中仍可追溯）。

### 5. `__init__.py` 里只有一行无用 import

`extractors/__init__.py` 内容是 `# extractors pkg`（21 字节），没有任何实际功能。应该在这里放共享基础设施（候选 A 方案）。

---

## 四、给 DeepSeek 的执行优先级建议

1. **P0**：修复 `env_vars.py` 的变量遮蔽 bug（`for p in p.parents`）
2. **P0**：修复 `deps.py` 的 `group(0)` → `group(1)`
3. **P1**：提取共享 `SKIP_DIRS` + `iter_project_files` + `safe_read` 到 `extractors/__init__.py`，消灭 7 处重复
4. **P1**：自动注册机制替代手写 try/except ×9
5. **P1**：`result.update()` 改成按模块名命名空间隔离
6. **P2**：requirements 文件收集所有变体而非只取第一个
7. **P2**：重写 `docs/SKILL_REFERENCE.md` 对齐 v2
8. **P2**：删除 `project_insight_v1.py`
9. **P3**：统一输出 schema / 每个 extractor 自带 `format_plain()`
10. **P3**：README 补充输出示例、安装方式、"仅限 Python"声明

---

以上就是完整的审查结果，尖子直接复制给 DeepSeek 干活。