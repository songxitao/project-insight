"""
依赖提取模块 — 从 pyproject.toml、requirements.txt 和安装脚本中提取依赖。

用法:
    from extractors.deps import run
    result = run("/path/to/project")
"""

import re
from pathlib import Path

from . import iter_project_files, safe_read

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
            deps.append(m.group(1).strip())
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
            result['requirements_deps'].extend(scan_requirements_txt(str(req_file)))

    # 安装脚本中的依赖
    for rel_f in iter_project_files(root, extensions=None):
        abs_f = root / rel_f
        if is_script_file(abs_f):
            pkgs = scan_install_commands(str(abs_f))
            if pkgs:
                result['install_scripts'].append({
                    'file': str(rel_f),
                    'packages': pkgs
                })

    return result


def format_plain(data: dict) -> str:
    lines = []
    pyproject = data.get('pyproject_deps', [])
    reqs = data.get('requirements_deps', [])
    install = data.get('install_scripts', [])

    if pyproject:
        lines.append(f"\n\U0001f4e6 pyproject.toml 依赖 ({len(pyproject)} 项):")
        for d in sorted(pyproject):
            lines.append(f"  \u2022 {d}")

    if reqs:
        lines.append(f"\n\U0001f4dc requirements 依赖 ({len(reqs)} 项):")
        for d in sorted(reqs):
            lines.append(f"  \u2022 {d}")

    if install:
        lines.append(f"\n\U0001f4dc 安装脚本中的依赖:")
        for s in install:
            lines.append(f"  {s['file']}: {', '.join(s.get('packages', []))}")

    return '\n'.join(lines)
