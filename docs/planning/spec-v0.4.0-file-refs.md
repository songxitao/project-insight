# Spec v0.4.0 — project-insight 能力边界扩展

> 从"省 token 提取器"到"防 CI 炸体检器"第一跳

## Motivation

在实际使用中发现 project-insight 存在 5 个能力盲区，触发点是 funclip-pro 重构后 CI 因 `Path("app_control.py")` 相对路径引用断裂而炸掉。当前 project-insight 只扫描绝对路径（`sys.path.insert`/`PYTHONPATH`），完全不知道项目中存在 `Path("xxx.py")`/`open("data.json")` 这样的相对路径引用。

本 spec 聚焦于终结这类事故，建立"重构安全"的诊断能力。
 
## Design Decisions（来自高级模型指导）

| # | 问题 | 决策 | 理由 |
|:--|:--|:--|:--|
| 1 | 独立模块还是扩展现有？ | **独立 `file_refs.py`** | paths 管绝对路径（环境迁移风险），file_refs 管相对路径（重构安全），问题域不同；pkgutil 架构本来就是为小模块设计的 |
| 2 | 误报控制 | **扩展名白名单** + **存在性校验** | `.py/.json/.yaml/.csv/.txt/.md` → high 置信度；无扩展名裸字符串直接过滤。存在性检查是天然过滤器 |
| 3 | 扫描范围 | **一期只 `.py`** | 二期再扩 `.md`。先做最高价值最小范围 |
| 4 | 断裂是否影响 exit code | **默认 warn，`--strict` 时 exit 1** | 不绑架普通用户，CI 场景自选用 |
| 5 | 与 local_graph 关系 | **独立但互补** | local_graph = 模块级引用（import 语义），file_refs = 文件系统级引用（磁盘语义） |

## 新增 / 修改模块清单

| 模块 | 操作 | 功能 |
|:---|:---|:---|
| `file_refs.py` | **新增** | 相对文件路径引用扫描 + 存在性校验 |
| `local_graph.py` | **扩展** | import 目标存在性回查（盲区 3） |
| `env_vars.py` | **补充** | 补齐 `os.environ["KEY"]` 等变体（盲区 4） |
| `project_insight.py` | **扩展** | 新增 `--strict` 标志 |
| `docs/SKILL_REFERENCE.md` | **更新** | 记录新模块 |
| 集成测试 | **新增** | 金样本快照测试 |

## 接口契约

所有新增/修改模块必须遵循现有规范：
- `run(root_dir: str) -> dict` — 每个模块返回命名空间隔离的 dict
- 可选 `format_plain(data: dict) -> str` — 控制纯文本输出格式
- 使用共享基础设施 `iter_project_files()` / `should_skip()` / `safe_read()`
- `pkgutil.iter_modules` 自动注册，零配置

## 版本约束

- Python >=3.8 兼容
- 零三方依赖
- 不破坏现有模块接口签名
- 现有 76 个测试全部保持绿色

## 执行策略

所有 ticket 严格按 **TDD 流程**执行：
1. 先写测试（定义期望行为）
2. 再写实现（使测试通过）
3. 运行全量测试确保无回归
4. 代码审查（Standards + Spec 双轴）
5. 提交
