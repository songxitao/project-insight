# T1 Spec: 共享基础设施层（候选 A）

## 目标

从 9 个 extractor 中提取**文件遍历、目录跳过、安全读取、自动注册**四项重复基础设施到 `extractors/__init__.py`，消灭约 100 行重复代码，消除变量遮蔽 bug，实现新增 extractor 零配置。

## 改动策略

**不改变任何 extractor 的 `run(root_dir: str) -> dict` 签名**，只改内部实现。

`project_insight.py` 的注册表从手写 try/except ×9 改为从 `extractors.__init__` 导入自动注册的 `REGISTRY`。

## 改动清单

### 文件 1：`extractors/__init__.py`（新建基础设施）

放入以下公共组件：

1. **`SKIP_DIRS`**（`frozenset`）— 统一跳过目录集合
2. **`should_skip(path: Path) -> bool`** — 检查路径的任意父目录是否在跳过列表中
3. **`iter_project_files(root: Path, extensions: tuple = ('.py',), key: str | None = None) -> Iterator[Path]`** — 遍历项目文件，自动跳过跳过目录和扩展名过滤
4. **`safe_read(filepath: Path | str, encoding='utf-8') -> str`** — 安全读取文件内容，出错返回空字符串
5. **`is_text_ext(ext: str, allowlist: tuple) -> bool`** — 判断扩展名是否在白名单中（供 `rglob('*')` 型 extractor 使用）
6. **`REGISTRY`**（dict）— 通过 `pkgutil.iter_modules` 自动注册所有带 `run()` 的 extractor

#### 设计细节

##### `iter_project_files`

```python
def iter_project_files(root: Path, extensions: tuple = ('.py',), key: str | None = None) -> Iterator[Path]:
    """遍历项目文件，返回相对于 root 的路径（相对路径策略）。"""
    for f in sorted(root.rglob('*')):
        if not f.is_file():
            continue
        if should_skip(f.relative_to(root)):
            continue
        if extensions and f.suffix.lower() not in extensions:
            continue
        yield f.relative_to(root)
```

- **相对路径策略**：yield 相对路径，调用方自行 `root / rel_path` 拼回绝对路径
- 如果 `extensions` 为 `None`（如 tree.py），不做扩展名过滤
- 使用 `root.rglob('*')` + `should_skip(f.relative_to(root))` 而非 `root.rglob('*.py')` + 检查 `p.parents`，因为相对路径更可靠

##### `should_skip`

```python
def should_skip(rel_path: Path) -> bool:
    """检查相对路径的任意部分是否在 SKIP_DIRS 中"""
    return any(part in SKIP_DIRS for part in rel_path.parts)
```

- 接收**相对于项目根的路径**，检查每个路径部分
- 自然地解决了 env_vars.py 中 `for p in p.parents` 的变量遮蔽 bug

##### 自动注册

```python
REGISTRY: dict[str, callable] = {}
for _, name, _ in pkgutil.iter_modules(__path__):
    try:
        mod = importlib.import_module(f".{name}", __package__)
        if hasattr(mod, 'run'):
            REGISTRY[name] = mod.run
    except Exception as e:
        import sys
        print(f"[WARN] extractor '{name}' 加载失败: {e}", file=sys.stderr)
```

- `hasattr(mod, 'run')` 天然过滤掉 `__init__.py`（不含 `run()`）
- tree.py 也有 `run()`，自动注册进入 `REGISTRY["tree"] = tree.run`

##### `SKIP_DIRS` 内容

```python
SKIP_DIRS = frozenset({
    '__pycache__', '.git', 'venv', '.venv', 'env',
    'node_modules', 'build', 'dist', '.pytest_cache',
    '.ruff_cache', '.workbuddy', 'output', 'outputs',
    'testset', 'model', 'models', 'checkpoints',
    '.pilot_venv', '.superpowers', '.agents', '.claude',
    '.scratch', '.egg-info', 'site-packages',
})
```

- 合并了 tree.py 中多出的 `'outputs'`, `'model'`, `'models'`, `'checkpoints'`（其他 extractor 缺失的）
- 移除了其他 extractor 中有但 tree.py 没有的 `'*.egg-info'`（glob pattern，不适合直接放入 `frozenset` 做成员检测）
- **不使用** tree.py 中的 `'__init__.py'` 作为 SKIP_DIRS 成员（会把项目中的所有 `__init__.py` 目录级过滤掉，破坏包结构）

##### `safe_read`

```python
def safe_read(filepath: Path | str, encoding='utf-8') -> str:
    try:
        return Path(filepath).read_text(encoding=encoding, errors='replace')
    except Exception:
        return ''
```

### 文件 2：`project_insight.py`（改造入口）

**删除**：第 23-78 行手写 try/except ×9 的注册表

**改为**：
```python
from extractors import REGISTRY

ALL_MODULES = sorted(REGISTRY.keys())
```

**同时改造输出循环**（适配命名空间）：
```python
result = {}
for module_name in selected_modules:
    runner = REGISTRY.get(module_name)
    if not runner:
        continue
    try:
        result[module_name] = runner(str(root_dir))
    except Exception as e:
        result[module_name] = {'error': str(e)}
```

改造 `_print_plain` 函数——从硬编码 22 个 if/elif key 分支，改为按模块名遍历 `result`：
- 每个模块的数据在 `result[module_name]` 下（命名空间策略）
- 模块各自的 key 是内部业务 key（如 `deps` 模块返回 `{"pyproject_deps": [...], "requirements_deps": [...], "install_scripts": [...]}`）
- `_print_plain` 先打印模块名标头，再根据内部 key 类型决定打印格式
- 保持与当前输出格式兼容：模块名作为分区标记，内部 key 按原有格式化逻辑输出

**改造原则**：`_print_plain` 不再逐一列举每个 key，而是按 `(module_name, inner_data)` 的两级结构做通用分发。但如果某个模块的输出格式特别特殊（如 tree 的递归打印），可作为特例保留。

### 文件 3-10：9 个 extractor，逐一改造

**通用模式**（每个 extractor 都改）：
1. 删掉行内定义的 skip set 或 `skip_dir()` / `_is_skip_dirs()` 函数
2. 遍历逻辑改为 `for rel_path in iter_project_files(root, extensions=(...,))`
3. 文件读取改为 `content = safe_read(root / rel_path)`（相对路径 + root 拼接）
4. `f.relative_to(root)` → 直接使用 `rel_path`（已是相对路径）

#### 各 extractor 具体改造

| Extractor | 当前遍历方式 | extensions | 特殊处理 |
|-----------|-------------|------------|---------|
| `deps.py` | `root.rglob('*')` + skip set + `is_script_file()` | `('.bat', '.sh', '.ps1', '')` 外加按文件名判断 Dockerfile | 保留 `is_script_file()` 留在自身模块；`run()` 中还需单独找 requirements\* 文件 |
| `entries.py` | `root.rglob('*.py')` + skip set | `('.py',)` | 保留 `_read_snippet()` 和 `_get_context_lines()`（这俩是专属逻辑） |
| `env_vars.py` | `root.rglob('*.py')` + `_is_skip_dirs()` | `('.py',)` 但还要额外扫 .env 和 docker-compose | 保留 `.env` / `docker-compose` 的扫描逻辑；`_is_skip_dirs()` 删除 |
| `imports.py` | `root.rglob('*.py')` + skip set | `('.py',)` | 保留 `scan_imports()` |
| `paths.py` | `root.rglob('*')` + skip set | `('.py', '.bat', '.sh', '.ps1', '')` 外加 Dockerfile 判断 | 扩展名过滤需包含所有脚本类文件 |
| `urls.py` | `root.rglob('*')` + `_is_skip_dirs()` | `('.py', '.bat', '.sh', '.ps1', '.yaml', '.yml', '.json', '.toml', '.cfg', '.ini', '.env', '.conf')` | `_is_skip_dirs()` 删除 |
| `model_refs.py` | `root.rglob('*')` + `_is_skip_dirs()` | `('.py', '.bat', '.sh', '.ps1', '.yaml', '.yml', '.json')` | `_is_skip_dirs()` 删除 |
| `local_graph.py` | `root.rglob('*.py')` + skip set（出现两遍） | `('.py',)` | `_collect_local_modules()` 和 `_get_source_imports()` 都改 |
| `tree.py` | 递归 `_build_tree()` 不走 rglob | 无 | 不动（tree 的树遍历不走 rglob，不需要换） |

## 验收标准

1. **无重复代码**：`SKIP_DIRS`、`should_skip`、`iter_project_files`、`safe_read` 只在 `__init__.py` 定义一次
2. **变量遮蔽 bug 消失**：`for p in p.parents` 不再出现（原 `env_vars.py` 第 119 行）
3. **自动注册**：`project_insight.py` 不再有手写 try/except，从 `extractors.REGISTRY` 导入
4. **命名空间隔离**：`result[module_name] = runner(root_dir)`，不再有 `result.update()`
5. **功能回归**：所有 9 个模块的输出与改造前一致（逐项对比验证）
6. **新增 extractor**：在 `extractors/` 目录下新建一个带 `run()` 的 `.py` 文件，无需修改任何现有代码即可自动注册
