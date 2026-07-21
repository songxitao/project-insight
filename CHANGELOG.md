# Changelog

## [0.3.1] - 2026-07-22

### Fixed

- `model_refs`: `MODEL_DIR_PATTERN` raw string `\\s` 转义 bug → 分 quoted/unquoted 双分支修复，`"save_dir"`/`"D:\models\qwen"` 等路径不再截断 (P0)
- `model_refs`: `MODEL_FILE_PATTERN` 加 `\w\.` 约束拒绝孤立扩展名（`".bin"` 等），`(?i:)` 支持大写扩展名（`"MODEL.PT"`）
- `model_refs`: JSON 文件 from 文本正则改为 `json.loads()` 结构化解析 + `looks_like_model_path()` 共享谓词，消除 weight_map 3000+ 行爆炸
- `model_refs`: `MODEL_DIR_PATTERN` unquoted 分支增加 `(` 排除，防止 `some_func(arg)` 误捕获
- `model_refs`: `looks_like_model_path()` 与 `MODEL_FILE_PATTERN` 语义对齐（`\w` → `[\w-]`），JSON/正则两路对连字符文件名行为一致

### Changed

- `model_refs`: Counter→list-of-dicts 转换 4 处重复提取为 `_freq_to_dict()` 共享函数（S1 重构）
- `model_refs`: 输出从 flat list 改为 `[{path, count}]` 频次计数格式（Counter 聚合，信息无损）
- `model_refs`: 扫描白名单扩展 `.md/.toml/.cfg/.ini`（README/config 中 `from_pretrained` 常见）
- `model_refs`: 测试从 7 个增至 24 个（DIR golden 表、JSON 路由、爆炸回归、语义对齐全覆盖）

### Removed

- `model_refs`: 移除对 `model.safetensors.index.json` 的正则扫描（显式跳过，模型元数据非引用代码）

## [0.3.0] - 2026-07-20

### Added

- 共享基础设施层：`extractors/__init__.py` 提供 `should_skip`、`iter_project_files`、`safe_read`、自动注册
- `format_plain()` 接口：env_vars、model_refs、tree、urls 各自实现独立格式化
- `[project.scripts]` CLI 入口：`pip install` 后可直接执行 `project-insight`
- README：输出示例、安装方式、`--modules` 用法说明
- 新增 deps 回归测试：尾部逗号场景、多 requirements 文件合并

### Changed

- JSON 输出从扁平结构改为命名空间：`{"deps": {...}, "tree": {...}}`
- `_print_plain` 改为通用分发器，删除 `_format_env_vars`/`_format_model_refs`/`_format_urls`
- `_format_generic` 返回 `str` 而非直接打印，提升可测试性
- `REGISTRY` 从 `{name: func}` 改为 `{name: {'run': func, 'mod': module}}`
- deps 的 `requirements_deps` 收集所有变体文件而非只取第一个
- `SKILL_REFERENCE.md` 重写对齐 v2 架构

### Fixed

- `env_vars.py` 变量遮蔽 bug：`for p in p.parents` 中循环变量覆盖函数参数
- `deps.py` 包名含尾部逗号：`group(0)` → `group(1)` 只取纯包名
- 删除 7 处重复的 skip set 定义，统一在 `__init__.py` 管理

### Removed

- `scripts/project_insight_v1.py` 及对应测试文件

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

### Fixed

- `tree` 模块：`_count_lines` 对大文件/二进制文件行数统计导致卡死，新增 `BINARY_EXTS` 二进制扩展名跳过 + `MAX_LINES_READ_MB=50` 文件大小保护
- `tree` 模块：`SKIP_DIRS` 补充 `outputs`/`model`/`models`/`checkpoints`，防止扫描模型权重目录或输出目录

## [0.1.0] - 2026-07-19

### Added

- 初始版本：单文件 `scripts/project_insight_v1.py`
- pyproject.toml 依赖提取
- requirements.txt 依赖提取
- 源码顶层 import 提取
- 安装脚本（.bat/.sh/Dockerfile）依赖提取
- 本地路径硬编码扫描
