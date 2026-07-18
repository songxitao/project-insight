"""
入口点与 API 端点模块 — 从 .py 文件中提取入口点和 API 路由。

用法:
    from extractors.entries import run
    result = run("/path/to/project")
"""

import re
from pathlib import Path


# 入口点正则
ENTRY_PATTERNS = [
    (re.compile(r"if\s+__name__\s*==\s*['\"]__main__['\"]"), 'main_guard'),
    (re.compile(r"app\s*=\s*(?:FastAPI|Flask|Sanic|Django)\s*\("), 'web_framework'),
    (re.compile(r"typer\.run\(|cli\.command|@click\.command"), 'cli_tool'),
    (re.compile(r"uvicorn\.run\(|gunicorn"), 'server_launcher'),
]

# API 端点正则
API_PATTERN = re.compile(
    r"@(?:app|router|api)\.\s*(?:get|post|put|delete|patch|route|websocket)\s*\(\s*['\"](.+?)['\"]"
)


def _read_snippet(filepath: str) -> str:
    """只读前 200 行和末尾 20 行"""
    try:
        with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
            lines = f.readlines()
    except Exception:
        return ''

    total = len(lines)
    if total <= 220:
        return ''.join(lines)

    head = ''.join(lines[:200])
    tail = ''.join(lines[-20:])
    return head + '\n# ... (skipped middle) ...\n' + tail


def _get_context_lines(lines: list, idx: int, max_lines: int, context: int = 2) -> str:
    """提取匹配行上下的上下文"""
    start = max(0, idx - context)
    end = min(max_lines, idx + context + 1)
    return '\n'.join(lines[start:end])


def run(root_dir: str) -> dict:
    """提取项目的入口点和 API 端点"""
    root = Path(root_dir)
    entry_points = []
    api_endpoints = []

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

        snippet = _read_snippet(str(f))
        if not snippet:
            continue

        lines = snippet.split('\n')
        rel = str(f.relative_to(root))

        # 匹配入口点
        for pattern, entry_type in ENTRY_PATTERNS:
            for i, line in enumerate(lines):
                # 跳过正则模式字符串定义（re.compile/r"...") 中的误匹配
                stripped_line = line.strip()
                if stripped_line.startswith('re.compile(') or \
                   stripped_line.startswith('(re.compile(') or \
                   'ENTRY_PATTERNS' in stripped_line or \
                   'PATTERN' in stripped_line:
                    continue
                if pattern.search(line):
                    ctx = _get_context_lines(lines, i, len(lines))
                    entry_points.append({
                        'file': rel,
                        'type': entry_type,
                        'line': i + 1,
                        'context': ctx,
                    })

        # 匹配 API 端点
        for i, line in enumerate(lines):
            m = API_PATTERN.search(line)
            if m:
                ctx = _get_context_lines(lines, i, len(lines))
                api_endpoints.append({
                    'file': rel,
                    'route': m.group(1),
                    'line': i + 1,
                    'context': ctx,
                })

    return {
        'entry_points': entry_points,
        'api_endpoints': api_endpoints,
    }
