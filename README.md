<p align="center">
  <img src="https://img.shields.io/badge/license-MIT-blue.svg" alt="License">
  <img src="https://img.shields.io/badge/python-%3E%3D3.8-blue.svg" alt="Python >=3.8">
  <img src="https://github.com/songxitao/project-insight/actions/workflows/ci.yml/badge.svg" alt="CI">
  <img src="https://img.shields.io/badge/PRs-welcome-brightgreen.svg" alt="PRs Welcome">
</p>

<p align="center">
  🎯 <a href="#-核心特性">核心特性</a>&nbsp&nbsp | &nbsp&nbsp 🏗️ <a href="#-架构设计">架构设计</a>&nbsp&nbsp | &nbsp&nbsp 🚀 <a href="#-闪电开始">闪电开始</a>&nbsp&nbsp | &nbsp&nbsp 📦 <a href="#-模块一览">模块一览</a>&nbsp&nbsp | &nbsp&nbsp 🔧 <a href="#-进阶调优">进阶调优</a>
</p>

# project-insight

**省 token 的 AI agent 项目信息提取器。用正则从项目中精准提取关键信息，替代全量读取。**

> ⚠️ 仅限 **Python 项目**（`.py` / `.toml` / `.yaml` / `.json` / `.md` 等文本文件）。二进制文件、模型权重、媒体文件不读不解析。

---

## 💡 项目背景

### 痛点

AI agent 在理解一个项目时，传统做法是**全量读取代码文件**——这不仅消耗大量 token、拖慢响应速度，还会让模型在非关键内容（模型权重、媒体文件、依赖锁定等）上分散注意力。一个中等规模的 Python 项目动辄数百个文件，逐文件全量读取的成本极高。

### 方案

**project-insight** 用**精准正则提取**替代全量读取。10 个专业扫描模块各司其职，从源码中提取**结构化摘要**——依赖清单、入口点、环境变量、模块依赖图等——以最少的 token 消耗让 AI agent 在毫秒级理解项目全貌。

---

## ✨ 核心特性

| 特性 | 痛点 | 方案 | 价值 |
|:---|:---|:---|:---|
| **🎯 精准正则提取** | 全量读取浪费 token，模型注意力被稀释 | 10 个专业模块用正则靶向提取关键信息 | **token 消耗降低 90%+** |
| **🧩 插件式自动发现** | 新增扫描逻辑需改动入口和注册表 | `pkgutil` 自动发现 + 命名空间隔离 | **新增模块零配置，即放即用** |
| **🏗️ 共享基础设施层** | 每个扫描器重复实现遍历/跳过低级逻辑 | 统一 `iter_project_files` / `should_skip` / `safe_read` | **消灭 7 份重复代码，新增跳过目录改一处生效** |
| **📊 命名空间输出** | 模块间 key 冲突导致数据静默覆盖 | `result[module_name] = runner(root)` | **每个模块独立命名空间，互不污染** |
| **🎨 格式化下沉** | 展示逻辑与核心提取耦合 | 每个模块可选实现 `format_plain()` | **展示逻辑下沉到模块，主入口只剩通用分发器** |
| **🔍 断裂引用检测** | 重构后路径断裂，CI 静默通过 | `file_refs` + `local_graph.broken_imports` + `--strict` 标志 | **CI 中自动拦截路径断裂事故** |

---

## 🏗️ 架构设计

```
scripts/
  └─ project_insight.py          ← CLI 入口 + 注册表 + 输出分发
  └─ extractors/
      ├─ __init__.py              ← 共享基础设施（遍历/跳过/读取/自动注册）
      ├─ deps.py                  ← 依赖提取
      ├─ entries.py               ← 入口点与 API 端点
      ├─ file_refs.py             ← 文件引用扫描
      ├─ env_vars.py              ← 环境变量引用
      ├─ imports.py               ← 顶层 import 提取
      ├─ local_graph.py           ← 本地模块依赖图
      ├─ model_refs.py            ← 模型/权重文件引用
      ├─ paths.py                 ← 本地硬编码路径
      ├─ tree.py                  ← 项目骨架树
      └─ urls.py                  ← 端口与 URL 硬编码
```

### 工作流

```
项目根目录 ──→ iter_project_files() ──→ 10 个提取器并行
                              ↓
                    should_skip() 过滤 × safe_read() 读取
                              ↓
                    每个提取器返回结构化 dict
                              ↓
                    REGISTRY 分发 + 命名空间合并
                              ↓
                ┌─── JSON 输出（AI agent 消费）
                └─── Plain 输出（人类可读）
```

### 注册发现机制

新增一个提取器只需在 `extractors/` 下创建带 `run()` 的 `.py` 文件——`pkgutil.iter_modules` 自动发现并注册，零配置：

```python
# extractors/__init__.py — 自动注册核心
for _, name, _ in pkgutil.iter_modules(__path__):
    mod = importlib.import_module(f".{name}", __package__)
    if hasattr(mod, 'run'):
        REGISTRY[name] = {'run': mod.run, 'mod': mod}
```

---

## 🚀 闪电开始

### 安装

```bash
# pip 安装
pip install project-insight

# 或直接运行
git clone https://github.com/songxitao/project-insight.git
cd project-insight
pip install -e .
```

### 极简启动

```bash
# 分析当前目录
project-insight

# 指定项目路径
project-insight /path/to/your/project

# JSON 结构化输出（推荐 AI agent 使用）
project-insight /path/to/your/project --format json

# 只运行指定模块
project-insight /path/to/your/project --modules "deps,imports,tree"
```

### 输出示例

```json
{
  "deps": {
    "pyproject_deps": ["requests>=2.28.0", "click"],
    "requirements_deps": ["flask", "pandas"],
    "install_scripts": [{"file": "setup.sh", "packages": ["torch"]}]
  },
  "tree": {
    "project_tree": {
      "path": ".",
      "children": [
        {"path": "src/main.py", "tag": "[入口]", "size_kb": 2.0, "lines": 50}
      ]
    }
  },
  "imports": {
    "source_imports": {
      "main.py": ["os", "sys", "json"],
      "utils.py": ["re", "pathlib"]
    }
  }
}
```

---

## 📦 模块一览

| 模块 | 功能 | 扫描范围 |
|:---|:---|:---|
| `deps` | 依赖提取 | `pyproject.toml`、`requirements*.txt`、安装脚本 |
| `imports` | 顶层 import 提取 | `.py` 文件顶层 `import`/`from` 语句 |
| `paths` | 本地路径硬编码扫描 | 脚本中的绝对路径引用 |
| `tree` | 项目骨架树 | 目录结构 + 文件角色标签（入口/测试/部署/文档） |
| `entries` | 入口点与 API 端点 | `if __name__ == '__main__'`、FastAPI/Flask 路由 |
| `file_refs` | 文件引用扫描 | `.py` 文件中 `Path("")` / `open("")` / subprocess 脚本引用，含存在性校验（**检测重构断裂**） |
| `env_vars` | 环境变量引用 | `os.environ.get()` / `os.getenv()` / `environ["KEY"]`、`.env` 文件、`docker-compose.yml` |
| `model_refs` | 模型/权重文件引用 | HuggingFace ID、`from_pretrained`、模型路径配置 |
| `urls` | 端口与 URL 硬编码 | 端口号、URL、IP 地址、localhost 引用 |
| `local_graph` | 本地模块依赖图 | 项目内模块引用关系分析 + **`broken_imports` 断裂引用检测** |

---

## 🔧 进阶调优

### 跳过目录

共享的跳过目录集在 `extractors/__init__.py` 的 `SKIP_DIRS` 中定义。新增跳过目录只需改一处：

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

### 自定义 extractor

1. 在 `scripts/extractors/` 下新建 `<模块名>.py`
2. 实现 `run(root_dir: str) -> dict`
3. 可选实现 `format_plain(data: dict) -> str` 控制展示格式
4. **无需修改任何现有代码**——自动注册

### strict 模式

新增 `--strict` / `-s` 标志，用于 CI 场景：

- **默认模式**：检测到断裂引用只输出 `[WARN]` 到 stderr，exit 0
- **`--strict` 模式**：检测到断裂引用直接 exit 1，让 CI pipeline 失败

```bash
# 默认模式：断裂引用仅警告
project-insight /path/to/project

# strict 模式：断裂引用即失败
project-insight /path/to/project --strict
```

与 `file_refs`（文件引用扫描）和 `local_graph`（broken_imports）配合使用，可在 CI 中自动拦截路径断裂问题。

---

## 🔬 测试

```bash
pip install pytest
pytest tests/ -v
```

当前 **113 个测试覆盖全部模块**，CI（GitHub Actions）在 Python 3.9~3.13 上全绿。

---

## 🤝 贡献指南

欢迎 PR！请确保：
- 新增 extractor 同时添加对应测试
- 保持 `run()` / `format_plain()` 接口签名不变
- 提交前通过 `pytest tests/` 全量测试

---

## 📄 许可

MIT License. 详见 [LICENSE](LICENSE)。
