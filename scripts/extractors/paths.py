"""
本地路径扫描模块 — 检测代码中的硬编码本地路径。

用法:
    from extractors.paths import run
    result = run("/path/to/project")
"""

import re
from pathlib import Path

from . import iter_project_files


PATH_PATTERN = re.compile(
    r'(?:sys\.path\.insert|sys\.path\.append|PYTHONPATH|PATH=)'
    r'[\s\(]*[\'"]?([a-zA-Z]:[\\/][^\'")\s]+)[\'"]?',
)


def scan_local_paths(filepath: str) -> list:
    """从文件找硬编码的本地路径"""
    content = Path(filepath).read_text(encoding='utf-8', errors='replace')
    return [m.group(1) for m in PATH_PATTERN.finditer(content)]


def run(root_dir: str) -> dict:
    """扫描项目中所有硬编码的本地路径"""
    root = Path(root_dir)
    result = []

    for rel_f in iter_project_files(root, extensions=None):
        f = root / rel_f
        ext = f.suffix.lower()
        if ext in ('.py', '.bat', '.sh', '.ps1') or \
           f.name.lower() in ('dockerfile', 'dockerfile.dev', 'dockerfile.prod'):
            paths = scan_local_paths(str(f))
            if paths:
                result.append({
                    'file': str(rel_f),
                    'paths': paths
                })

    return {'local_paths': result}
