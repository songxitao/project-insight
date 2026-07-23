"""
Import 提取模块 — 从 .py 文件提取顶层 import。

用法:
    from extractors.imports import run
    result = run("/path/to/project")
"""

import re
from pathlib import Path

from . import iter_project_files, safe_read


IMPORT_PATTERN = re.compile(
    r'^(?:import|from)\s+([a-zA-Z0-9_\.]+)', re.MULTILINE
)


def scan_imports(filepath: str) -> set:
    """从 .py 文件提取顶层 import（只保留根名）"""
    full_imports = scan_imports_full(filepath)
    return {imp.split('.')[0] for imp in full_imports}


def scan_imports_full(filepath: str) -> set:
    """从 .py 文件提取顶层 import，返回完整 import 路径（不截断根名）。

    保留 'scripts.extractors.deps' 而非截断为 'scripts'。
    """
    content = safe_read(filepath)
    if not content:
        return set()
    lines = content.split('\n')
    imports = set()
    in_docstring = False
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith(('"""', "'''")):
            if stripped.count('"""') >= 2 or stripped.count("'''") >= 2:
                continue
            in_docstring = not in_docstring
            continue
        if in_docstring:
            continue
        if stripped.startswith('#'):
            continue
        m = IMPORT_PATTERN.match(stripped)
        if m:
            full = m.group(1)
            root = full.split('.')[0]
            if root != '__future__':
                imports.add(full)
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
