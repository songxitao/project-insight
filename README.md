# project-insight

![CI](https://github.com/songxitao/project-insight/actions/workflows/ci.yml/badge.svg)

省 token 的 AI agent 项目信息提取器。用正则从项目中精准提取关键信息，替代全量读取。

> ⚠️ 仅限 **Python 项目**（`.py` / `.toml` / `.yaml` / `.json` / `.md` 等文本文件）。
> 二进制文件、模型权重、媒体文件不读不解析。

## 安装

```bash
pip install project-insight
```

或直接运行脚本：

```bash
python scripts/project_insight.py /path/to/project
```

## 用法

```bash
# 纯文本输出（默认）
project-insight /path/to/project

# JSON 结构化输出
project-insight /path/to/project --format json

# 指定模块
project-insight /path/to/project --modules "deps,imports,tree"
```

### 输出示例（JSON）

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
  }
}
```

## 模块

| 模块 | 功能 |
|------|------|
| deps | pyproject.toml / requirements.txt 依赖提取 |
| imports | 源码顶层 import 提取 |
| paths | 本地路径硬编码扫描 |
| tree | 项目骨架树（目录结构+角色标签） |
| entries | 入口点与 API 端点 |
| env_vars | 环境变量依赖 |
| model_refs | 模型/权重文件引用 |
| urls | 端口与 URL 硬编码 |
| local_graph | 本地模块依赖图 |

## 设计原则

- **只读文本**：只扫描代码文本文件，不读二进制/模型/媒体文件
- **精准提取**：用正则替代全量读取，省 token
- **自动发现**：新增 extractor 放进目录即可，零配置注册
- **命名空间隔离**：每个模块的输出互不污染

## 测试

```bash
pip install pytest
pytest tests/
```

## 许可

MIT
