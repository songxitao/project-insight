---
name: project-insight
description: 省 token 的 AI agent 项目信息提取器。用正则从项目中精准提取依赖、import、安装脚本和本地路径硬编码，输出结构化摘要，避免 agent 全量读取代码浪费 token。
---

# project-insight — 项目快速洞察工具

## 定位

**省 token 的 AI agent 项目信息提取器。** 用正则从项目中精准提取关键信息，不给 agent 喂全量代码。

解决的核心痛点：AI agent 对接项目时总忍不住全量 Read 文件，浪费大量 token。本脚本代替 agent 做定向读取，输出结构化摘要。

## 前置条件

- Python 3.8+
- 目标目录应是 Python 项目（有 .py 文件）

## 核心脚本

`scripts/qc_extract_deps.py` — 依赖提取 + 本地路径扫描

用法：
```bash
# JSON 格式（推荐给 agent 消费）
<python> scripts/qc_extract_deps.py /path/to/project --format json

# 纯文本格式（给人看）
<python> scripts/qc_extract_deps.py /path/to/project
```

## 四类正则扫描模式

### 1. pyproject.toml / requirements.txt 依赖提取
只从 `[project]dependencies` 段提取，不读文件其他部分。
```
[project].*?dependencies\s*=\s*\[(.*?)\]
```

### 2. 源码顶层 import 提取
只读每个 .py 文件的顶层 import，检测到 `def/class/@` 立即停止。
```
^(?:import|from)\s+([a-zA-Z0-9_\.]+)
```

### 3. 安装脚本依赖提取
从 .bat/.sh/Dockerfile 中找 pip/conda install 命令。
```
(?:pip|conda|mamba)\s+install\s+(.+?)(?:&&|\||$)
```

### 4. 本地路径硬编码扫描
找 sys.path.insert/PYTHONPATH 中的 Windows 绝对路径。
```
(?:sys\.path\.insert|sys\.path\.append|PYTHONPATH|PATH=)[\s\(]*[\'"]?([a-zA-Z]:[\\/][^'")\s]+)
```

## 输出格式

JSON 输出包含 4 个字段：
| 字段 | 类型 | 说明 |
|------|------|------|
| `pyproject_deps` | string[] | pyproject.toml 声明的依赖列表 |
| `source_imports` | object | key=文件路径，value=该文件顶层 import 的包名列表 |
| `install_scripts` | object[] | 安装脚本中的依赖包 |
| `local_paths` | object[] | 本地路径硬编码发现 |

## 典型用途

| 场景 | 命令 | 节省 token 比例 |
|------|------|:--------------:|
| 查项目所有依赖 | `--format json` | ~95% |
| 找重型 ML 依赖 | 从 JSON 中 grep torch/onnxruntime/tensorflow | ~95% |
| CI 依赖 vs 全量依赖差异分析 | 结合 requirements.lock 对比 | ~90% |
| 查本地路径硬编码 | 查看 local_paths 字段 | ~99% |

## 与现有 skill 的关系

| skill | 关系 |
|-------|------|
| `demo-to-oss` | 可在 METADATA 维度被调用，提供 pyproject.toml 依赖信息 |
| `oss-guard` | 互补——oss-guard 管安全审计，project-insight 管依赖和项目结构洞察 |
| `project-docking` | 可作为快速了解项目的第一个步骤 |
| `project-onboarding` | 可提供依赖摘要作为上手指南的一部分 |
