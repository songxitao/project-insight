"""
本地模块依赖图模块 — 利用 imports 数据判断哪些 import 指向项目内部模块。

用法:
    from extractors.local_graph import run
    result = run("/path/to/project")
"""

from pathlib import Path
import re


def _collect_local_modules(root: Path) -> dict:
    """收集项目内的 Python 模块名，注册所有可能的模块名变体。

    考虑两种场景：
    - Python 搜索路径包含项目根目录（模块名 = scripts.extractors.deps）
    - Python 搜索路径包含 scripts 等子目录（模块名 = extractors.deps）
    """
    modules = {}

    # 收集所有 .py 文件
    for f in root.rglob('*.py'):
        if not f.is_file():
            continue
        if any(p.name in {'__pycache__', '.git', 'venv', '.venv', 'env',
                          'node_modules', 'build', 'dist', '.pytest_cache',
                          '.ruff_cache', '.workbuddy', 'output', 'testset',
                          '.pilot_venv', '.superpowers', '.agents', '.claude',
                          '.scratch'}
               for p in f.parents):
            continue
        rel = f.relative_to(root)
        parts = list(rel.parts)

        # 去掉 .py 后缀
        parts[-1] = parts[-1][:-3] if parts[-1].endswith('.py') else parts[-1]

        # 如果文件是 __init__.py，用目录路径作为模块名
        if parts[-1] == '__init__':
            module_path = '.'.join(parts[:-1])
        else:
            module_path = '.'.join(parts)

        if module_path:
            modules[module_path] = str(rel)

            # 也注册所有子路径变体（去掉顶层目录前缀）
            # 例如 scripts.extractors.deps → extractors.deps
            dot_parts = module_path.split('.')
            for i in range(1, len(dot_parts)):
                sub_path = '.'.join(dot_parts[i:])
                if sub_path not in modules:
                    modules[sub_path] = str(rel)

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
    from extractors.imports import scan_imports
    root = Path(root_dir)
    result = {}
    for f in sorted(root.rglob('*.py')):
        if not f.is_file():
            continue
        if any(p.name in {'__pycache__', '.git', 'venv', '.venv', 'env',
                          'node_modules', 'build', 'dist', '.pytest_cache',
                          '.ruff_cache', '.workbuddy', 'output', 'testset',
                          '.pilot_venv', '.superpowers', '.agents', '.claude',
                          '.scratch'}
               for p in f.parents):
            continue
        imports = scan_imports(str(f))
        if imports:
            result[str(f.relative_to(root))] = imports
    return result


def run(root_dir: str) -> dict:
    """构建本地模块依赖图"""
    root = Path(root_dir)
    local_modules = _collect_local_modules(root)
    source_imports = _get_source_imports(root_dir)

    local_dep_graph = {}

    for file_path, imports in source_imports.items():
        local_refs = []
        for imp in imports:
            # 收集所有匹配的本地模块名
            candidates = []
            for mod_name in local_modules:
                if imp == mod_name:
                    # 精确匹配优先
                    candidates.insert(0, mod_name)
                elif imp == mod_name.split('.')[0]:
                    candidates.append(mod_name)
            # 按匹配质量排序：精确匹配 > 前缀匹配（按深度，最浅优先）
            if candidates:
                # 选择精确匹配（如果有），否则选择最浅的包
                exact = [c for c in candidates if c == imp]
                if exact:
                    local_refs.append(exact[0])
                else:
                    # 按层级排序，选最浅（最高层包名）
                    candidates.sort(key=lambda x: len(x.split('.')))
                    local_refs.append(candidates[0])
        if local_refs:
            local_dep_graph[file_path] = sorted(set(local_refs))

    return {
        'local_dep_graph': local_dep_graph,
    }
