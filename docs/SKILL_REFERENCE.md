# SKILL_REFERENCE — project-insight

## 概述

project-insight 是一个 AI agent 项目信息提取器，用正则从代码中精准提取关键信息，替代全量读取。

## 架构

```
scripts/
  project_insight.py          ← 主入口（CLI + 注册表 + 输出格式化）
  extractors/
    __init__.py                ← 共享基础设施 + 自动注册
    deps.py                    ← 依赖提取（pyproject / requirements）
    entries.py                 ← 入口点与 API 端点
    env_vars.py                ← 环境变量引用
    imports.py                 ← 顶层 import 提取
    local_graph.py             ← 本地模块依赖图
    model_refs.py              ← 模型/权重文件引用
    paths.py                   ← 本地硬编码路径
    tree.py                    ← 项目骨架树
    urls.py                    ← 端口与 URL 硬编码
```

## 关键设计

### 共享基础设施（`extractors/__init__.py`）

- `SKIP_DIRS` — 统一跳过目录 frozenset
- `should_skip(rel_path)` — 目录跳过检测
- `iter_project_files(root, extensions)` — 文件遍历生成器
- `safe_read(filepath)` — 安全读取文本文件
- `REGISTRY` — 自动注册的 extractor 字典：`{name: {'run': func, 'mod': module}}`

### 注册与发现

新增 extractor：在 `extractors/` 下新建一个带 `run()` 和可选 `format_plain()` 的 `.py` 文件即可，无需修改任何现有代码。

### 输出协议

- `run(root_dir: str) -> dict` — 每个 extractor 的入口
- `format_plain(data: dict) -> str` — 可选，自定义纯文本格式化
- `REGISTRY[name]['mod']` 有 `format_plain` → 主入口调用它，否则走通用格式化

### 结果结构

```json
{
  "deps": {"pyproject_deps": [...], "requirements_deps": [...], "install_scripts": [...]},
  "entries": {"entry_points": [...], "api_endpoints": [...]},
  "env_vars": {"env_vars": {...}, "env_vars_summary": [...]},
  "imports": {"source_imports": {...}},
  "local_graph": {"local_dep_graph": {...}},
  "model_refs": {"model_refs": [...], "model_refs_summary": {...}},
  "paths": {"local_paths": [...]},
  "tree": {"project_tree": {...}},
  "urls": {"hardcoded_urls": [...], "hardcoded_urls_summary": {...}}
}
```

## 用法

```bash
# 默认 plain 格式
python scripts/project_insight.py /path/to/project

# JSON 输出
python scripts/project_insight.py /path/to/project --format json

# 指定模块
python scripts/project_insight.py /path/to/project --modules "deps,imports,tree"
```

## 测试

```bash
cd <project-root>
pip install pytest
pytest tests/
```

## 扩展指南

1. 在 `scripts/extractors/` 下新建 `<模块名>.py`
2. 实现 `run(root_dir: str) -> dict`
3. 可选：实现 `format_plain(data: dict) -> str`
4. 在 `tests/` 下新建测试文件
5. 运行测试验证

新增 extractor 无需修改 `__init__.py` 或 `project_insight.py`。
