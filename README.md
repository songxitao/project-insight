# project-insight

省 token 的 AI agent 项目信息提取器。用正则从项目中精准提取关键信息，替代全量读取。

## 用法

```bash
python scripts/project_insight.py /path/to/project --format json
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
