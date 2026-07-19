"""
Import 提取模块 — 从 .py 文件提取顶层 import。

用法:
    from extractors.imports import run
    result = run("/path/to/project")
"""

import re
from pathlib import Path

from . import iter_project_files


IMPORT_PATTERN = re.compile(
    r'^(?:import|from)\s+([a-zA-Z0-9_\.]+)', re.MULTILINE
)


def scan_imports(filepath: str) -> set:
    """从 .py 文件提取顶层 import（不读函数体内部的 import）"""
    content = Path(filepath).read_text(encoding='utf-8')
    lines = content.split('\n')
    imports = set()
    in_docstring = False
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue

        # 跟踪文档字符串（跳过 """ 和 ''' 之间的内容）
        if stripped.startswith(('"""', "'''")):
            if stripped.count('"""') >= 2 or stripped.count("'''") >= 2:
                # 单行文档字符串，跳过
                continue
            in_docstring = not in_docstring
            continue
        if in_docstring:
            continue

        # 跳过注释行
        if stripped.startswith('#'):
            continue

        m = IMPORT_PATTERN.match(stripped)
        if m:
            root = m.group(1).split('.')[0]
            if root != '__future__':
                imports.add(root)
        if stripped.startswith(('def ', 'class ', '@')):
            break
    return imports


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
    lines = [f"\n🔗 源码 import ({len(source_imports)} 个文件):"]
    for f, imps in sorted(source_imports.items()):
        lines.append(f"  {f} → {', '.join(sorted(imps))}")
    return '\n'.join(lines)
