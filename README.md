<p align="center">
  <img src="https://img.shields.io/badge/license-MIT-blue.svg" alt="License">
  <img src="https://img.shields.io/badge/python-%3E%3D3.8-blue.svg" alt="Python >=3.8">
  <img src="https://github.com/songxitao/project-insight/actions/workflows/ci.yml/badge.svg" alt="CI">
  <img src="https://img.shields.io/badge/PRs-welcome-brightgreen.svg" alt="PRs Welcome">
  <img src="https://img.shields.io/github/stars/songxitao/project-insight" alt="Stars">
</p>

<p align="center">
  🎯 <a href="#-这工具到底干嘛的">这工具到底干嘛的</a>&nbsp&nbsp | &nbsp&nbsp 🚀 <a href="#-快速上手">快速上手</a>&nbsp&nbsp | &nbsp&nbsp 🏗️ <a href="#-架构一览">架构一览</a>&nbsp&nbsp | &nbsp&nbsp 📦 <a href="#-扫描模块清单">模块清单</a>&nbsp&nbsp | &nbsp&nbsp 🔧 <a href="#-进阶用法">进阶用法</a>
</p>

# project-insight

**把你的项目扔给 AI 之前，先跑一遍 project-insight。AI 花 1 秒读完摘要，而不是 10 分钟读你所有代码。**

> ⚠️ 目前仅支持 **Python 项目**（`.py` / `.toml` / `.yaml` / `.json` / `.md` 等文本文件）。二进制文件、模型权重、媒体文件不读不解析。

---

## 🎯 这工具到底干嘛的

### 一句话

AI agent（Claude、GPT、Cursor、Copilot 这类）要理解一个项目时，传统做法是把几百个代码文件全读一遍——烧钱又慢。`project-insight` 用正则扫一遍你的项目目录，输出一份**结构化摘要**，AI 读完摘要就能了解项目全貌，不用真去翻文件。

### 三个使用场景

| 场景 | 痛点 | project-insight 能干嘛 |
|:---|:---|:---|
| **🤖 AI 接入项目** | 给 Claude/Cursor 一个新项目，它要读半天文件才能干活 | 跑一份 JSON 摘要喂给 AI，它秒懂项目用了什么依赖、有什么入口、环境变量是什么 |
| **🔍 重构安全检查** | 你移动了一个文件，但忘了还有人用 `Path("old_path.py")` 引用它，CI 炸了 | `patterns` 模块扫出所有路径引用 + 存在性检查，`--strict` 模式让 CI 直接拦截 |
| **📋 项目快速概览** | 新同事加入项目，想快速了解项目结构和技术选型 | `tree` 看目录骨架，`deps` 看依赖，`imports` 看模块组织，`patterns` 看有哪些入口/路径/URL |

### 一个输出例子

```json
# project-insight /path/to/project --format json
{
  "deps": {
    "pyproject_deps": ["requests>=2.28.0", "click"],
    "requirements_deps": ["flask", "pandas"]
  },
  "tree": {
    "project_tree": { "path": ".", "size_kb": 120, "files": 34 }
  },
  "imports": {
    "source_imports": {
      "main.py": ["os", "sys", "json", "flask"],
      "utils.py": ["re", "pathlib", "numpy"]
    }
  },
  "patterns": {
    "urls": [...],
    "paths": [...],
    "entry_points": [...],
    "file_refs": [...]
  },
  "env_vars": {
    "env_vars_summary": [
      {"name": "API_KEY", "required": true, "sources": [".env"]}
    ]
  }
}
```

---

## 📣 更新日志

### v0.5.0 — 2026-07-24

- **重大重构**: `imports` 正则→AST 重写，使用 `ast.parse()` 替代正则+手动 docstring 状态机
- **重大重构**: `deps` 双路径——A 路 pipreqs/deptry CLI，B 路 AST+映射表零依赖底线
- **重大重构**: 新增 `patterns` 模块，坍缩 urls/paths/entries/file_refs 四个 extractor 为配置项驱动
- **移除**: 删除 urls.py、paths.py、entries.py、file_refs.py 四个旧文件
- **测试**: 旧测试迁移至 `tests/legacy/` 并 skip，新增 patterns 测试

### v0.4.1 — 2026-07-24

- **修复**: `env_vars` 重复匹配 bug（6 条 pattern 合并为 4 条）
- **修复**: `local_graph` import 路径截断导致断裂检测失准
- **修复**: `file_refs` 漏报 `pathlib.Path("file.py")` 带模块前缀的情况
- **改进**: 删除各处死代码，`safe_read` 统一使用
- **README**: 重写为价值导向的描述方式

### v0.4.0 — 2026-07-23

- **新增**: `file_refs` 模块——扫描 `Path("")`/`open("")`/subprocess 三种相对路径引用，检查文件是否存在
- **新增**: `--strict` / `-s` 标志——检测到断裂引用时 exit 1，CI 可用
- **新增**: `local_graph.broken_imports`——import 目标存在性回查
- **新增**: `env_vars` 补齐 `environ["KEY"]`/`environ.setdefault()` 等变体
- **新增**: 端到端集成测试（10 模块全量验证）
- 当前 **113 个测试**，CI 全绿

---

## 🚀 快速上手

```bash
# 1. 下载
git clone https://github.com/songxitao/project-insight.git
cd project-insight
pip install -e .

# 带依赖扫描工具（推荐）：
pip install -e ".[deps]"

# 2. 运行
project-insight /path/to/your/project

# 3. JSON 输出（推荐给 AI agent 用）
project-insight /path/to/your/project --format json
```

不安装也行，直接跑：

```bash
python scripts/project_insight.py /path/to/your/project --format json
```

### 只扫你关心的

```bash
# 只看依赖和目录结构
project-insight . --modules "deps,tree"

# 查文件引用断裂
project-insight . --modules "patterns,local_graph" --strict
```

---

## 🏗️ 架构一览

```
scripts/
  └─ project_insight.py          ← CLI 入口 + 分发
  └─ extractors/
      ├─ __init__.py              ← 共享工具（遍历/跳过/读取）+ 自动注册
      ├─ deps.py                  ← 依赖（双路径：CLI / AST 零依赖底线）
      ├─ env_vars.py              ← 环境变量
      ├─ imports.py               ← import（AST 解析）
      ├─ local_graph.py           ← 本地依赖图
      ├─ model_refs.py            ← 模型引用
      ├─ patterns.py              ← 路径/URL/入口/文件引用（配置项驱动）
      └─ tree.py                  ← 项目骨架
```

所有模块共享同一套遍历/跳过/读取基础设施，新增一个模块只需建文件 + 写 `run()` 函数：

> **deps 双路径说明**：A 路通过 pipreqs/deptry CLI 获取精确依赖（需 `pip install project-insight[deps]`）；B 路纯 AST+包名映射表实现零外部依赖兜底，无需安装任何额外工具即可运行。

```python
# extractors/__init__.py — 自动注册
for _, name, _ in pkgutil.iter_modules(__path__):
    mod = importlib.import_module(f".{name}", __package__)
    if hasattr(mod, 'run'):
        REGISTRY[name] = {'run': mod.run, 'mod': mod}
```

---

## 📦 扫描模块清单

| 模块 | 它告诉你什么 | 为什么有用 |
|:---|:---|:---|
| `deps` | 项目依赖了哪些包（双路径：CLI / AST 零依赖底线） | 一眼看出技术栈，无外部工具也能跑 |
| `imports` | 每个文件 import 了什么（AST 解析） | 理解模块依赖关系，精度更高 |
| `tree` | 目录结构 + 文件角色标签 | 快速熟悉项目骨架 |
| `patterns` | 硬编码路径、URL/端口、入口点、文件引用 — 统一配置项驱动 | **重构断裂检测 + 环境迁移预警** |
| `env_vars` | 需要配置哪些环境变量 | 部署时不会漏配 |
| `model_refs` | 模型文件、HuggingFace 引用 | AI 项目必备 |
| `local_graph` | 项目内模块的引用关系 | **import 断裂检测** |

---

## 🔧 进阶用法

### `--strict` / `-s` — CI 拦截模式

```bash
# 默认：断裂引用只警告，不中断
project-insight /path/to/project

# strict：检测到断裂引用就 exit 1，CI pipeline 会失败
project-insight /path/to/project --strict
```

### 自定义跳过目录

所有提取器共享跳过列表，改一处生效：

```python
SKIP_DIRS = frozenset({
    '__pycache__', '.git', 'venv', 'node_modules',
    'build', 'dist', '.pytest_cache', '.ruff_cache',
    'model', 'models', 'checkpoints', 'output', 'outputs',
    '.agents', '.claude', '.scratch', '.egg-info',
})
```

### 自己写一个 extractor

```python
# scripts/extractors/my_scanner.py
from . import iter_project_files

def run(root_dir: str) -> dict:
    # 你的扫描逻辑
    return {'my_scanner': [...]}

def format_plain(data: dict) -> str:
    # 可选：控制纯文本输出格式
    return '\n'.join(...)
```

放进去就自动注册，不用改任何现有代码。

---

## 🔬 测试

```bash
pytest tests/ -v
```

**113 个测试覆盖全部模块**，CI（GitHub Actions）在 Python 3.9~3.13 上全绿。

---

## 🤝 贡献指南

欢迎 PR！请遵守：
- 新增模块同时加测试
- 保持 `run()` / `format_plain()` 接口签名
- 提交前 `pytest tests/` 全量通过

---

## 📄 许可

MIT License. 详见 [LICENSE](LICENSE)。
