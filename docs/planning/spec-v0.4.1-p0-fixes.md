# Spec v0.4.1 — P0 Debug Plan (Flash Model 可执行)

> 从 v0.4.0 code review 提取的 3 个 P0 阻塞 bug，每项精确到行号 + 修复代码 + 验证命令。
>
> **目标模型**：flash / lite 模型。**核心原则**：每一步都是机械操作，不需要推理。

---

## 前置：验证当前基线

```bash
cd E:\project\project-insight
python -m pytest tests/ -q --tb=short
```

期望：**116 passed, 1 failed (test_print_plain — pre-existing, 无需处理)**

---

## Fix #1 — `env_vars.py`：合并重复 pattern + 修复 `[\s*'"]` 字符类

**严重性**：P0 · **文件**：`scripts/extractors/env_vars.py` · **行号**：16-23

### 当前代码（有问题）

```python
PYTHON_ENV_PATTERNS = [
    re.compile(r"os\.environ\.get\(\s*['\"](.+?)['\"]"),        # line 17
    re.compile(r"os\.environ\[[\s*'\"](.+?)['\"]"),             # line 18 ← 字符类错误
    re.compile(r"os\.getenv\(\s*['\"](.+?)['\"]"),              # line 19
    re.compile(r"environ\.get\(\s*['\"](.+?)['\"]"),            # line 20 ← 与 line17 重复
    re.compile(r"environ\[[\s*'\"](.+?)['\"]"),                # line 21 ← 字符类错误 + 与 line18 重复
    re.compile(r"(?:os\.)?environ\.setdefault\(\s*['\"](.+?)['\"]"),  # line 22
]
```

两个 bug：
1. **line 20 匹配子串**：`environ.get` 会匹配 `os.environ.get` 的尾部 → 同一个 `os.environ.get("KEY")` 被 line 17 和 line 20 各匹配一次 → 重复计数
2. **line 18 和 line 21 的 `[\s*'"]`**：这是字符类，匹配 `\s`（空格）或 `*`（星号字面量）或 `'` 或 `"` 共 4 个字符中**任意一个**。正确意图是"可选空格 + 引号"，应写为 `\s*['"]`。触发场景：`environ[ "KEY"]` 时字符类吃掉第一个空格，捕获组从 `"` 开始，最终 `m.group(1)` = `"KEY`（含前导引号）

### 修复后代码（直接替换 line 16-23）

```python
PYTHON_ENV_PATTERNS = [
    re.compile(r"(?:os\.)?environ\.get\(\s*['\"](.+?)['\"]"),              # 合并 line17+line20
    re.compile(r"(?:os\.)?environ\[\s*['\"](.+?)['\"]"),                   # 合并 line18+line21，修复字符类
    re.compile(r"os\.getenv\(\s*['\"](.+?)['\"]"),                         # 不变
    re.compile(r"(?:os\.)?environ\.setdefault\(\s*['\"](.+?)['\"]"),       # 不变
]
```

**变更要点**：
- line 17+20 合并为 1 条：`(?:os\.)?environ\.get`
- line 18+21 合并为 1 条：`(?:os\.)?environ\[` 且 `[\s*'"]` → `\s*['"]`
- 从 6 条减至 4 条

### 验证命令

```bash
cd E:\project\project-insight
python -m pytest tests/test_env_vars.py -v
```

期望：全部 16 个测试 PASSED（所有现有测试直接通过，因为修复后匹配结果更干净且不丢匹配）

---

## Fix #2 — `local_graph.py`：让 `scan_imports` 返回完整 import 路径

**严重性**：P0 · **文件**：`scripts/extractors/imports.py` + `scripts/extractors/local_graph.py`

### 根因

`imports.py:47` 行 `root = m.group(1).split('.')[0]` 把 `import scripts.extractors.deps` 截断为 `scripts`。然后 `local_graph.py:89-97` 的匹配逻辑用这个截断后的根名去 match `local_modules`。

**后果**：
- `import mypkg.deep.module` 且 `mypkg/__init__.py` 存在 → 判定为 local_ref（只检查了 `mypkg`，没检查 `mypkg.deep.module` 是否真的存在）
- `import broken_pkg.missing` 且 `broken_pkg/__init__.py` 存在 → 同上，漏报 broken

### Step 1：修改 `imports.py` — 保留完整路径

**文件**：`scripts/extractors/imports.py` · **行号**：20-52

目标：新增一个函数 `scan_imports_full()`，返回完整 import 路径而非只返回根名。

在 `scan_imports()` 函数**下方**（line 53 之前）新增：

```python
def scan_imports_full(filepath: str) -> set:
    """从 .py 文件提取顶层 import，返回完整 import 路径（不截断根名）。

    与 scan_imports() 的区别：保留 'scripts.extractors.deps' 而非截断为 'scripts'。
    """
    content = Path(filepath).read_text(encoding='utf-8')
    lines = content.split('\n')
    imports = set()
    in_docstring = False
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith(('"""', "'''")):
            if stripped.count('"""') >= 2 or stripped.count("'''") >= 2:
                continue
            in_docstring = not in_docstring
            continue
        if in_docstring:
            continue
        if stripped.startswith('#'):
            continue
        m = IMPORT_PATTERN.match(stripped)
        if m:
            full = m.group(1)           # ← 唯一改动：不 split('.')[0]
            root = full.split('.')[0]
            if root != '__future__':
                imports.add(full)        # ← 存完整路径
        if stripped.startswith(('def ', 'class ', '@')):
            break
    return imports
```

**不改动现有 `scan_imports()`**，避免影响 `imports.py` 自身输出（它只展示顶层 import 根名是合理的）。

### Step 2：修改 `local_graph.py` — 使用完整路径 + 完善匹配逻辑

**文件**：`scripts/extractors/local_graph.py` · **行号**：64-74

将 `_get_source_imports` 中的 `scan_imports` 调用替换为 `scan_imports_full`：

```python
def _get_source_imports(root_dir: str) -> dict:
    """提取所有 .py 文件的顶层 import（复用 imports 模块逻辑）"""
    from extractors.imports import scan_imports_full      # ← 改这里
    root = Path(root_dir)
    result = {}
    for rel_f in iter_project_files(root, extensions=('.py',)):
        f = root / rel_f
        imports = scan_imports_full(str(f))               # ← 改这里
        if imports:
            result[str(rel_f)] = imports
    return result
```

### Step 3：修改 `local_graph.py` — 完善匹配逻辑以处理完整路径

**文件**：`scripts/extractors/local_graph.py` · **行号**：86-113

当前 `imp` 是根名如 `scripts`，修改后 `imp` 是完整路径如 `scripts.extractors.deps`。需要更新匹配逻辑：

将第 89-113 行替换为：

```python
        for imp in imports:
            # imp 现在是完整路径如 "scripts.extractors.deps"
            matched = None

            # 1. 精确匹配（最高优先级）
            if imp in local_modules:
                matched = imp
            else:
                # 2. 前缀匹配：找以 imp 开头的未知模块
                #    例如 imp="scripts.extractors.missing" 不在 local_modules 中
                #    但 scripts.extractors 在 → 取其作为近似匹配
                parts = imp.split('.')
                for i in range(len(parts) - 1, 0, -1):
                    prefix = '.'.join(parts[:i])
                    if prefix in local_modules:
                        matched = prefix
                        break

            if matched is None:
                # 3. 根名 fallback：只匹配第一段
                root = imp.split('.')[0]
                candidates = [m for m in local_modules
                              if m == root or m.split('.')[0] == root]
                if candidates:
                    candidates.sort(key=lambda x: len(x.split('.')))
                    matched = candidates[0]

            if matched is not None:
                if (root / local_modules[matched]).exists():
                    local_refs.append(matched)
                else:
                    broken_refs.append(matched)
```

### 验证命令

```bash
cd E:\project\project-insight
python -m pytest tests/test_local_graph.py tests/test_imports.py -v
```

期望：
- `test_imports.py`：全部 PASSED（`scan_imports` 未被修改）
- `test_local_graph.py`：全部 PASSED（现有测试应通过；如果 `test_cross_file_import_creates_edge` 因 import 路径变化失败，需要更新该测试中 `local_dep_graph` 的 key 从 `utils` → 完整路径）

额外验证：对 project-insight 自身运行：
```bash
python scripts/project_insight.py E:\project\project-insight --modules local_graph --format json
```
检查输出中 `local_dep_graph` 的 key 是否有类似 `scripts.extractors.deps` 的完整路径。

---

## Fix #3 — `file_refs.py`：支持 `pathlib.Path()` 带模块前缀

**严重性**：P0 · **文件**：`scripts/extractors/file_refs.py` · **行号**：25-27

### 当前代码

```python
QUOTED_REF_PATTERN = re.compile(
    r"""(?P<type>Path|open)\s*\(\s*["'](?P<path>[^"']+)["']\s*\)"""
)
```

问题：`(?:pathlib\.)?` 未出现，不匹配 `pathlib.Path("file.py")`

### 修复后代码

```python
QUOTED_REF_PATTERN = re.compile(
    r"""(?P<type>(?:pathlib\.)?Path|open)\s*\(\s*["'](?P<path>[^"']+)["']\s*\)"""
)
```

就一行改动：`Path` → `(?:pathlib\.)?Path`。

### 验证命令

```bash
cd E:\project\project-insight
python -m pytest tests/test_file_refs.py -v
```

期望：全部 11 个测试 PASSED。

额外验证——手动测试 `pathlib.Path()`：

```python
# 在 Python REPL 中执行
import re
QUOTED_REF_PATTERN = re.compile(
    r"""(?P<type>(?:pathlib\.)?Path|open)\s*\(\s*["'](?P<path>[^"']+)["']\s*\)"""
)
# 测试
m1 = QUOTED_REF_PATTERN.search('pathlib.Path("config.json")')
print(m1.group('type'))  # 应为 pathlib.Path
print(m1.group('path'))  # 应为 config.json

m2 = QUOTED_REF_PATTERN.search('Path("app.py")')
print(m2.group('type'))  # 应为 Path
print(m2.group('path'))  # 应为 app.py
```

---

## 全量回归验证

完成 3 个 Fix 后：

```bash
cd E:\project\project-insight
python -m pytest tests/ -q --tb=short
```

期望：116 passed, 1 failed (test_print_plain — pre-existing)。如果多出失败，检查 test_local_graph.py 的 test_cross_file_import_creates_edge 和 test_multiple_dependencies — 可能需要将 `local_dep_graph` 断言中的 key 从简写模块名更新为完整路径。

---

## Fix 顺序

```
Fix #1 (env_vars) → Fix #2 (local_graph) → Fix #3 (file_refs)
```

原因：Fix #1 最简单（纯替换），先做建立信心。Fix #2 最复杂（跨文件改动 + 匹配逻辑重写），可能波及测试。Fix #3 单行改动，最后收尾。

每个 Fix 完成后立即跑该模块的测试确认通过，再进入下一个。
