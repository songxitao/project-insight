"""
本地路径扫描模块 — 检测代码中的硬编码本地路径。

用法:
    from extractors.paths import run
    result = run("/path/to/project")
"""

import re
from pathlib import Path


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

    for f in sorted(root.rglob('*')):
        if not f.is_file():
            continue
        if any(p.name in {'__pycache__', '.git', 'venv', '.venv', 'env',
                          'node_modules', 'build', 'dist', '.pytest_cache',
                          '.ruff_cache', '.workbuddy', 'output', 'testset',
                          '.pilot_venv', '.superpowers', '.agents', '.claude',
                          '.scratch'}
               for p in f.parents):
            continue
        ext = f.suffix.lower()
        if ext in ('.py', '.bat', '.sh', '.ps1') or \
           f.name.lower() in ('dockerfile', 'dockerfile.dev', 'dockerfile.prod'):
            paths = scan_local_paths(str(f))
            if paths:
                result.append({
                    'file': str(f.relative_to(root)),
                    'paths': paths
                })

    return {'local_paths': result}
