"""
依赖提取模块 — 从 pyproject.toml、requirements.txt 和安装脚本中提取依赖。

用法:
    from extractors.deps import run
    result = run("/path/to/project")
"""

import re
from pathlib import Path

DEP_PATTERN = re.compile(
    r'^[\s\'"]*([a-zA-Z0-9_\-\.]+(?:\[[a-zA-Z0-9_,\-\.]+\])?)'
    r'(?:\s*[><=!~]+\s*[\d.*,\s]+)?'
    r'(?:\s*[,;]|$)',
    re.MULTILINE
)

INSTALL_PATTERN = re.compile(
    r'(?:pip|conda|mamba)\s+install\s+(.+?)(?:&&|\||$)',
    re.IGNORECASE
)


def scan_pyproject(filepath: str) -> list:
    """从 pyproject.toml 提取依赖（仅读 [project]dependencies 段）"""
    content = Path(filepath).read_text(encoding='utf-8')
    m = re.search(r'\[project\].*?dependencies\s*=\s*\[(.*?)\]', content, re.DOTALL)
    if not m:
        return []
    raw = m.group(1)
    return [line.strip().strip('"').strip("'").rstrip(',')
            for line in raw.split('\n')
            if line.strip() and not line.strip().startswith('#')]


def scan_requirements_txt(filepath: str) -> list:
    """从 requirements.txt 文件提取依赖（含变体）。"""
    content = Path(filepath).read_text(encoding='utf-8', errors='replace')
    deps = []
    for line in content.split('\n'):
        stripped = line.strip()
        if not stripped or stripped.startswith('#'):
            continue
        if stripped.startswith(('-r', '-e', '--', '-c', '-f')):
            continue
        no_comment = stripped.split(' #', 1)[0].split('\t#', 1)[0].strip()
        m = DEP_PATTERN.match(no_comment)
        if m:
            deps.append(m.group(0).strip())
    return deps


def scan_install_commands(filepath: str) -> list:
    """从 .bat / .sh / Dockerfile 找安装命令中的依赖"""
    content = Path(filepath).read_text(encoding='utf-8', errors='replace')
    found = []
    for m in INSTALL_PATTERN.finditer(content):
        pkgs = re.findall(r'([a-zA-Z0-9_\-\.]+(?:==[\d.*]+)?)', m.group(1))
        found.extend(pkgs)
    return found


def is_script_file(f: Path) -> bool:
    """判断是否为安装脚本类文件"""
    ext = f.suffix.lower()
    if ext in ('.bat', '.sh', '.ps1'):
        return True
    if f.name.lower() in ('dockerfile', 'dockerfile.dev', 'dockerfile.prod'):
        return True
    return False


def skip_dir(name: str) -> bool:
    skip_dirs = {'__pycache__', '.git', 'venv', '.venv', 'env',
                 'node_modules', 'build', 'dist', '.pytest_cache',
                 '.ruff_cache', '.workbuddy', 'output', 'testset',
                 '.pilot_venv', '.superpowers', '.agents', '.claude',
                 '.scratch', '.egg-info', '*.egg-info', 'site-packages'}
    return name in skip_dirs


def run(root_dir: str) -> dict:
    """提取项目依赖信息"""
    root = Path(root_dir)
    result = {
        'pyproject_deps': [],
        'requirements_deps': [],
        'install_scripts': [],
    }

    # pyproject.toml
    pyproject = root / 'pyproject.toml'
    if pyproject.exists():
        result['pyproject_deps'] = scan_pyproject(str(pyproject))

    # requirements.txt 及其常见变体
    req_candidates = [
        'requirements.txt',
        'requirements-dev.txt',
        'requirements_dev.txt',
        'requirements-dev.lock',
        'requirements.lock',
        'requirements-test.txt',
    ]
    for req_name in req_candidates:
        req_file = root / req_name
        if req_file.exists():
            result['requirements_deps'] = scan_requirements_txt(str(req_file))
            break

    # 安装脚本中的依赖
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
        if is_script_file(f):
            pkgs = scan_install_commands(str(f))
            if pkgs:
                result['install_scripts'].append({
                    'file': str(f.relative_to(root)),
                    'packages': pkgs
                })

    return result
