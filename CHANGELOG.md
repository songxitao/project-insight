# Changelog

## [0.2.0] - 2026-07-19

### Added

- 架构重构：将单文件 `project_insight_v1.py` 重构为多模块结构 (`scripts/extractors/`)
- 新增 `tree` 模块：项目骨架树，递归扫描目录结构并标注角色标签（入口/测试/部署/文档/配置）
- 新增 `entries` 模块：入口点与 API 端点提取，仅读文件前 200 行和末尾 20 行
- 新增 `env_vars` 模块：环境变量提取（Python os.environ/.env/docker-compose）
- 新增 `local_graph` 模块：本地模块依赖图，分析项目内模块引用关系
- 新增 `model_refs` 模块：模型/权重文件引用扫描（onnx/pt/safetensors/HuggingFace ID）
- 新增 `urls` 模块：端口与 URL 硬编码检测
- 新增 `--modules` 参数支持按需选择扫描模块

### Changed

- `deps` 模块：从 v1 中独立出 pyproject/requirements/install 依赖提取
- `imports` 模块：从 v1 中独立出顶层 import 提取，增加文档字符串跳过逻辑
- `paths` 模块：从 v1 中独立出本地路径硬编码扫描

## [0.1.0] - 2026-07-19

### Added

- 初始版本：单文件 `scripts/project_insight_v1.py`
- pyproject.toml 依赖提取
- requirements.txt 依赖提取
- 源码顶层 import 提取
- 安装脚本（.bat/.sh/Dockerfile）依赖提取
- 本地路径硬编码扫描
