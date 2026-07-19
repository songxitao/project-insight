# 开源就绪检查报告

**项目**: project-insight
**扫描时间**: 2026-07-20
**技术栈**: Python >=3.8

## 总览

| 维度 | 状态 | 摘要 |
|------|------|------|
| LEGAL | ✅ | MIT License，pyproject.toml 许可字段一致 |
| METADATA | ✅ | 版本号 0.3.0 与 CHANGELOG 一致，URL 非占位符 |
| DOCS | ✅ | README / CHANGELOG / .gitignore 均已就绪，CI badge 为动态 |
| CI/QUALITY | ✅ | GitHub Actions 覆盖全部 10 个测试文件，pre-commit 已配置 |
| HYGIENE | ⚠️ | 无 CONTRIBUTING.md（可选） |
| SECURITY | ⚠️ | oss-guard 5 项检查：2 项 PASS、3 项 WARN（无 FAIL） |

## 修复建议（按优先级）

### 🟡 建议修（影响专业度）

#### 1. .gitignore 补充高危条目
Git 历史扫描发现 5 处"疑似密钥泄露"——均为误报（测试函数名 `test_req************` 匹配了 40 字符正则），当前代码无真实密钥泄露。

但 `.gitignore` 缺失三类高危条目：

| 分类 | 缺失条目 |
|------|---------|
| ML 模型权重 | `*.safetensors`, `*.bin`, `*.onnx`, `*.pt`, `*.pth`, `*.h5`, `*.pkl` |
| 密钥/凭证 | `.env`, `.env.*`, `*.pem`, `*.key` |
| 数据文件 | `*.csv`, `*.parquet`, `*.arrow` |

**修复方式**：向 `.gitignore` 追加：
```gitignore
# Build artifacts
*.pyc
*.egg
.eggs/
.tox/
.mypy_cache/

# ML weights
*.safetensors
*.bin
*.onnx
*.pt
*.pth
*.h5
*.pkl

# Credentials
.env
.env.*
*.pem
*.key

# Data
*.csv
*.parquet
*.arrow

# IDE
.vscode/
.idea/
*.swp
*.swo

# OS
.DS_Store
Thumbs.db
```

#### 2. pre-commit 增加安全 hook
当前 pre-commit 只有 ruff，建议增加体积/密钥检查步骤，防止误提交。

### 🔵 可选（锦上添花）

- 创建 `CONTRIBUTING.md` 标准模板
- CI 中增加安全审计步骤

---

*报告由 demo-to-oss 自动生成*
