"""
环境变量提取模块 — 从 .py/.env/docker-compose 中提取环境变量引用。

用法:
    from extractors.env_vars import run
    result = run("/path/to/project")
"""

import re
from pathlib import Path
from collections import defaultdict


PYTHON_ENV_PATTERNS = [
    re.compile(r"os\.environ\.get\(\s*['\"](.+?)['\"]"),
    re.compile(r"os\.environ\[[\s*'\"](.+?)['\"]"),
    re.compile(r"os\.getenv\(\s*['\"](.+?)['\"]"),
]

ENV_FILE_PATTERN = re.compile(r"^([A-Z][A-Z0-9_]+)\s*=", re.MULTILINE)


def _extract_from_python(filepath: str) -> list:
    """从 .py 文件中提取环境变量引用"""
    try:
        content = Path(filepath).read_text(encoding='utf-8', errors='replace')
    except Exception:
        return []

    results = []
    for pattern in PYTHON_ENV_PATTERNS:
        for m in pattern.finditer(content):
            var_name = m.group(1)
            required = True
            default = None

            line = content[:m.end()].split('\n')[-1]

            # 检查是否有默认值
            if 'environ.get' in line or 'getenv' in line:
                # 看行末是否有 default
                after_match = content[m.end():].split('\n')[0].strip()
                if after_match.startswith(','):
                    # 提取 default 值
                    # 简单判断：如果第一个 token 不是 )，则有默认值
                    rest = after_match[1:].strip()
                    if rest.startswith(')'):
                        required = False
                    elif rest.startswith("'"):
                        idx = rest.find("'", 1)
                        if idx > 0:
                            default = rest[1:idx]
                            required = False
                    elif rest.startswith('"'):
                        idx = rest.find('"', 1)
                        if idx > 0:
                            default = rest[1:idx]
                            required = False
                    else:
                        # 非字面量（如变量名），标记为有默认值但无法提取
                        required = False
                        default = '<dynamic>'
                elif after_match.startswith(')'):
                    required = False

            entry = {'name': var_name, 'required': required}
            if default is not None:
                entry['default'] = default
            results.append(entry)

    return results


def _extract_from_env(filepath: str) -> list:
    """从 .env 文件中提取环境变量"""
    try:
        content = Path(filepath).read_text(encoding='utf-8', errors='replace')
    except Exception:
        return []

    return [m.group(1) for m in ENV_FILE_PATTERN.finditer(content)]


def _extract_from_docker_compose(filepath: str) -> list:
    """从 docker-compose.yml 中提取 environment 段"""
    try:
        content = Path(filepath).read_text(encoding='utf-8', errors='replace')
    except Exception:
        return []

    results = []
    # 找 environment: 段
    m = re.search(r'environment:\s*\n((?:\s+-?\s*[A-Z_]+.*\n?)+)', content)
    if m:
        block = m.group(1)
        for line in block.split('\n'):
            line = line.strip().lstrip('- ')
            if not line:
                continue
            # KEY=VALUE 格式
            kv = re.match(r'([A-Z][A-Z0-9_]+)\s*=\s*(.*)', line)
            if kv:
                results.append({'name': kv.group(1), 'value': kv.group(2)})
                continue
            # 纯 KEY 格式
            key = re.match(r'([A-Z][A-Z0-9_]+)\s*$', line)
            if key:
                results.append({'name': key.group(1)})

    return results


def _is_skip_dirs(p: Path) -> bool:
    skip = {'__pycache__', '.git', 'venv', '.venv', 'env',
            'node_modules', 'build', 'dist', '.pytest_cache',
            '.ruff_cache', '.workbuddy', 'output', 'testset',
            '.pilot_venv', '.superpowers', '.agents', '.claude',
            '.scratch'}
    return any(p.name in skip for p in p.parents)


def run(root_dir: str) -> dict:
    """提取项目中的环境变量引用"""
    root = Path(root_dir)

    grouped = {
        'python_sources': [],
        'env_files': [],
        'docker_compose': [],
    }

    # 扫描所有 .py 文件
    for f in sorted(root.rglob('*.py')):
        if not f.is_file() or _is_skip_dirs(f):
            continue
        envs = _extract_from_python(str(f))
        if envs:
            grouped['python_sources'].append({
                'file': str(f.relative_to(root)),
                'variables': envs,
            })

    # 扫描 .env / .env.example
    for env_name in ('.env', '.env.example', '.env.local', '.env.prod', '.env.dev'):
        env_file = root / env_name
        if env_file.exists():
            keys = _extract_from_env(str(env_file))
            if keys:
                grouped['env_files'].append({
                    'file': env_name,
                    'keys': keys,
                })

    # 扫描 docker-compose.yml
    for dc_name in ('docker-compose.yml', 'docker-compose.yaml'):
        dc_file = root / dc_name
        if dc_file.exists():
            envs = _extract_from_docker_compose(str(dc_file))
            if envs:
                grouped['docker_compose'].append({
                    'file': dc_name,
                    'variables': envs,
                })

    # 去重汇总
    all_vars = defaultdict(list)
    for entry in grouped['python_sources']:
        for var in entry['variables']:
            name = var['name']
            key = (name, var['required'])
            source = entry['file']
            all_vars[key].append(source)
    for entry in grouped['env_files']:
        for key in entry['keys']:
            k = (key, False)
            all_vars[k].append(entry['file'])
    for entry in grouped['docker_compose']:
        for var in entry['variables']:
            name = var['name']
            k = (name, True)
            all_vars[k].append(entry['file'])

    summary = []
    for (name, required), sources in sorted(all_vars.items()):
        summary.append({
            'name': name,
            'required': required,
            'sources': list(set(sources)),
        })

    return {
        'env_vars': grouped,
        'env_vars_summary': summary,
    }
