"""
Import 提取模块 — 从 .py 文件提取顶层 import。

用法:
    from extractors.imports import run
    result = run("/path/to/project")

v0.5.0: 用 ast.parse() 替代正则 + 手动 docstring 状态机。
"""

import ast
from pathlib import Path

from . import iter_project_files, safe_read


def scan_imports_full(filepath: str) -> set:
    """从 .py 文件提取顶层 import，返回完整 import 路径。

    保留 'scripts.extractors.deps' 而非截断为 'scripts'。
    __future__ import 被过滤。
    """
    try:
        tree = ast.parse(Path(filepath).read_text(encoding='utf-8'))
    except SyntaxError:
        return set()

    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module and node.level == 0:
                imports.add(node.module)

    # 过滤 __future__
    return {imp for imp in imports if not imp == '__future__' and not imp.startswith('__future__.')}


def scan_imports(filepath: str) -> set:
    """从 .py 文件提取顶层 import（只保留根名）"""
    full_imports = scan_imports_full(filepath)
    # 过滤 __future__（依据根名）
    return {imp.split('.')[0] for imp in full_imports if imp.split('.')[0] != '__future__'}


def run(root_dir: str) -> dict:
    """提取所有 .py 文件的顶层 import"""
    root = Path(root_dir)
    result = {}

    for rel_f in iter_project_files(root, extensions=('.py',)):
        f = root / rel_f
        imports = scan_imports(str(f))
        if imports:
            result[str(rel_f)] = sorted(imports)

    return {'source_imports': result}


def format_plain(data: dict) -> str:
    source_imports = data.get('source_imports', {})
    if not source_imports:
        return ''
    lines = [f"\n\U0001F517 源码 import ({len(source_imports)} 个文件):"]
    for f, imps in sorted(source_imports.items()):
        lines.append(f"  {f} \u2192 {', '.join(sorted(imps))}")
    return '\n'.join(lines)
