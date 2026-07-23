"""
本地模块依赖图模块 — 利用 imports 数据判断哪些 import 指向项目内部模块。

用法:
    from extractors.local_graph import run
    result = run("/path/to/project")
"""

from pathlib import Path
import re

from . import iter_project_files


def _collect_local_modules(root: Path) -> dict:
    """收集项目内的 Python 模块名，注册所有可能的模块名变体。

    考虑两种场景：
    - Python 搜索路径包含项目根目录（模块名 = scripts.extractors.deps）
    - Python 搜索路径包含 scripts 等子目录（模块名 = extractors.deps）
    """
    modules = {}

    # 收集所有 .py 文件
    for rel_f in iter_project_files(root, extensions=('.py',)):
        parts = list(rel_f.parts)

        # 去掉 .py 后缀
        parts[-1] = parts[-1][:-3] if parts[-1].endswith('.py') else parts[-1]

        # 如果文件是 __init__.py，用目录路径作为模块名
        if parts[-1] == '__init__':
            module_path = '.'.join(parts[:-1])
        else:
            module_path = '.'.join(parts)

        if module_path:
            modules[module_path] = str(rel_f)

            # 也注册所有子路径变体（去掉顶层目录前缀）
            # 例如 scripts.extractors.deps → extractors.deps
            dot_parts = module_path.split('.')
            for i in range(1, len(dot_parts)):
                sub_path = '.'.join(dot_parts[i:])
                if sub_path not in modules:
                    modules[sub_path] = str(rel_f)

            # 注册父包
            parent_parts = parts[:-1]
            for i in range(len(parent_parts)):
                parent_path = '.'.join(parent_parts[:i + 1])
                if parent_path and parent_path not in modules:
                    modules[parent_path] = str(Path(*parent_parts[:i + 1]) / '__init__.py')
                # 父包也注册变体
                parent_dot_parts = parent_path.split('.')
                for j in range(1, len(parent_dot_parts)):
                    sub_parent = '.'.join(parent_dot_parts[j:])
                    if sub_parent not in modules:
                        modules[sub_parent] = str(Path(*parent_parts[:i + 1]) / '__init__.py')

    return modules


def _get_source_imports(root_dir: str) -> dict:
    """提取所有 .py 文件的顶层 import（复用 imports 模块逻辑）"""
    from extractors.imports import scan_imports_full
    root = Path(root_dir)
    result = {}
    for rel_f in iter_project_files(root, extensions=('.py',)):
        f = root / rel_f
        imports = scan_imports_full(str(f))
        if imports:
            result[str(rel_f)] = imports
    return result


def run(root_dir: str) -> dict:
    """构建本地模块依赖图"""
    root = Path(root_dir)
    local_modules = _collect_local_modules(root)
    source_imports = _get_source_imports(root_dir)

    local_dep_graph = {}
    broken_imports = {}

    for file_path, imports in source_imports.items():
        local_refs = []
        broken_refs = []
        for imp in imports:
            # imp 现在是完整路径如 "scripts.extractors.deps"
            matched = None

            # 1. 精确匹配（最高优先级）
            if imp in local_modules:
                matched = imp
            else:
                # 2. 前缀匹配：找以 imp 开头的未知模块
                #    例如 imp="scripts.extractors.missing" 不在 local_modules 中
                #    但 scripts.extractors 在 → 取其作为近似匹配
                parts = imp.split('.')
                for i in range(len(parts) - 1, 0, -1):
                    prefix = '.'.join(parts[:i])
                    if prefix in local_modules:
                        matched = prefix
                        break

            if matched is None:
                # 3. 根名 fallback：只匹配第一段
                root_name = imp.split('.')[0]
                candidates = [m for m in local_modules
                              if m == root_name or m.split('.')[0] == root_name]
                if candidates:
                    candidates.sort(key=lambda x: len(x.split('.')))
                    matched = candidates[0]

            if matched is not None:
                if (root / local_modules[matched]).exists():
                    local_refs.append(matched)
                else:
                    broken_refs.append(matched)

        if local_refs:
            local_dep_graph[file_path] = sorted(set(local_refs))
        if broken_refs:
            broken_imports[file_path] = sorted(set(broken_refs))

    return {
        'local_dep_graph': local_dep_graph,
        'broken_imports': broken_imports,
    }


def format_plain(data: dict) -> str:
    """将本地模块依赖图格式化为纯文本输出"""
    lines = []
    graph = data.get('local_dep_graph', {})
    if graph:
        lines.append(f"\n🔀 本地模块依赖图 ({len(graph)} 条):")
        for f, refs in sorted(graph.items()):
            lines.append(f"  {f} → {', '.join(refs)}")

    broken = data.get('broken_imports', {})
    if broken:
        lines.append(f"\n⚠️  断裂引用 ({sum(len(v) for v in broken.values())} 处):")
        for f, refs in sorted(broken.items()):
            lines.append(f"  {f} → {', '.join(refs)}")

    return '\n'.join(lines)
