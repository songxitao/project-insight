"""
依赖提取模块 — 双路径：A 路 pipreqs+deptry CLI（精确）/ B 路 AST+映射表（零依赖底线）。

用法:
    from extractors.deps import run
    result = run("/path/to/project")
"""

import re
import shutil
import subprocess
import sys
from pathlib import Path

try:
    import tomllib
except ImportError:
    try:
        import tomli as tomllib  # type: ignore[no-redef]
    except ImportError:
        print("[deps] tomllib 和 tomli 均不可用，pyproject.toml 解析回退到正则", file=sys.stderr)
        tomllib = None

from . import iter_project_files


def _get_stdlib_modules() -> frozenset:
    """获取标准库模块名集合（Python 3.10+ 用 sys.stdlib_module_names，低版本用硬编码列表）"""
    if hasattr(sys, 'stdlib_module_names'):
        return frozenset(sys.stdlib_module_names)
    # Python 3.8-3.9 兼容
    return frozenset({
        'os', 'sys', 're', 'json', 'math', 'time', 'datetime', 'pathlib',
        'collections', 'itertools', 'functools', 'typing', 'abc', 'io',
        'base64', 'binascii', 'bisect', 'calendar', 'csv', 'copy',
        'decimal', 'enum', 'filecmp', 'fnmatch', 'fractions', 'getpass',
        'glob', 'hashlib', 'heapq', 'hmac', 'html', 'http', 'importlib',
        'inspect', 'locale', 'logging', 'multiprocessing', 'operator',
        'optparse', 'os.path', 'pickle', 'platform', 'pprint', 'queue',
        'random', 're', 'secrets', 'select', 'shlex', 'shutil',
        'signal', 'socket', 'sqlite3', 'statistics', 'string', 'struct',
        'subprocess', 'sysconfig', 'tarfile', 'tempfile', 'textwrap',
        'threading', 'tokenize', 'traceback', 'tracemalloc', 'types',
        'unittest', 'urllib', 'uuid', 'warnings', 'weakref', 'xml',
        'zipfile', '__future__',
    })


# import 名 → pip 包名 映射表（>= 50 条）
THIRD_PARTY_MAP = {
    'PIL': 'Pillow', 'cv2': 'opencv-python', 'sklearn': 'scikit-learn',
    'yaml': 'PyYAML', 'bs4': 'beautifulsoup4', 'scipy': 'scipy',
    'torch': 'torch', 'tensorflow': 'tensorflow', 'flask': 'Flask',
    'django': 'Django', 'fastapi': 'fastapi', 'pydantic': 'pydantic',
    'requests': 'requests', 'selenium': 'selenium', 'numpy': 'numpy',
    'pandas': 'pandas', 'matplotlib': 'matplotlib', 'seaborn': 'seaborn',
    'plotly': 'plotly', 'dash': 'dash', 'streamlit': 'streamlit',
    'click': 'click', 'typer': 'typer', 'rich': 'rich',
    'sqlalchemy': 'SQLAlchemy', 'alembic': 'Alembic', 'psycopg2': 'psycopg2-binary',
    'redis': 'redis', 'pymongo': 'pymongo', 'motor': 'motor',
    'pytest': 'pytest', 'hypothesis': 'hypothesis', 'tox': 'tox',
    'celery': 'Celery', 'gunicorn': 'gunicorn', 'uvicorn': 'uvicorn',
    'httpx': 'httpx', 'aiohttp': 'aiohttp', 'websockets': 'websockets',
    'grpc': 'grpcio', 'protobuf': 'protobuf', 'cryptography': 'cryptography',
    'jwt': 'PyJWT', 'oauthlib': 'oauthlib', 'sphinx': 'Sphinx',
    'flake8': 'flake8', 'black': 'black', 'isort': 'isort',
    'mypy': 'mypy', 'ruff': 'ruff', 'pre_commit': 'pre-commit',
    'tqdm': 'tqdm', 'loguru': 'loguru', 'pydantic_settings': 'pydantic-settings',
    'dotenv': 'python-dotenv',
}

# requirements 文件名候选
REQ_CANDIDATES = [
    'requirements.txt',
    'requirements-dev.txt',
    'requirements_dev.txt',
    'requirements-dev.lock',
    'requirements.lock',
    'requirements-test.txt',
]


def _parse_pyproject(filepath: str) -> list:
    """解析 pyproject.toml 提取 [project]dependencies"""
    # 优先 tomllib/tomli
    if tomllib is not None:
        try:
            with open(filepath, 'rb') as f:
                data = tomllib.load(f)
            raw = data.get('project', {}).get('dependencies', [])
            if raw:
                return [d.strip() for d in raw if d.strip()]
        except Exception:
            pass
    # fallback: 正则匹配
    content = Path(filepath).read_text(encoding='utf-8', errors='replace')
    m = re.search(r'\[project\].*?dependencies\s*=\s*\[(.*?)\]', content, re.DOTALL)
    if not m:
        return []
    raw = m.group(1)
    result = []
    for line in raw.split('\n'):
        stripped = line.strip()
        if not stripped or stripped.startswith('#'):
            continue
        for ch in ('"', "'"):
            stripped = stripped.strip(ch)
        stripped = stripped.rstrip(',').strip()
        for ch in ('"', "'"):
            stripped = stripped.strip(ch)
        stripped = stripped.strip()
        if stripped:
            result.append(stripped)
    return result


def _parse_requirements(filepath: str) -> list:
    """解析 requirements.txt 提取包名"""
    content = Path(filepath).read_text(encoding='utf-8', errors='replace')
    deps = []
    for line in content.split('\n'):
        stripped = line.strip()
        if not stripped or stripped.startswith('#'):
            continue
        if stripped.startswith(('-r', '-e', '--', '-c', '-f')):
            continue
        no_comment = stripped.split(' #', 1)[0].split('\t#', 1)[0].strip()
        m = re.match(r'^[\s\'"]*([a-zA-Z0-9_\-\.]+(?:\[[a-zA-Z0-9_,\-\.]+\])?)', no_comment)
        if m:
            deps.append(m.group(1).strip())
    return deps


def _imports_to_packages(root_dir: str) -> list[dict]:
    """复用 imports.py 的 AST scan_imports_full → 过滤 stdlib → 映射为包名"""
    from extractors.imports import scan_imports_full  # noqa: PLC0415

    root = Path(root_dir)
    stdlib = _get_stdlib_modules()
    packages = {}

    for rel_f in iter_project_files(root, extensions=('.py',)):
        f = root / rel_f
        imports = scan_imports_full(str(f))
        for imp in imports:
            root_name = imp.split('.')[0]
            if root_name in stdlib:
                continue
            pkg_name = THIRD_PARTY_MAP.get(root_name, root_name)
            if pkg_name not in packages:
                packages[pkg_name] = {'name': pkg_name, 'count': 0}
            packages[pkg_name]['count'] += 1

    return sorted(packages.values(), key=lambda x: -x['count'])


def _clean_pkg_name(dep: str) -> str:
    """从依赖字符串中提取纯包名（去掉版本约束）"""
    name = re.split(r'[><=!~]+', dep)[0].strip()
    # 去掉 extras（如 [security]）
    if '[' in name:
        name = name.split('[')[0].strip()
    return name


def _run_b_route(root: Path) -> dict:
    """B 路：AST 扫描 → stdlib 过滤 → 映射 → pyproject.toml → requirements.txt"""
    # AST 扫描
    ast_deps = _imports_to_packages(str(root))

    # pyproject.toml
    pyproject_path = root / 'pyproject.toml'
    pyproject_deps = _parse_pyproject(str(pyproject_path)) if pyproject_path.exists() else []

    # requirements.txt 变体
    requirements_deps = []
    for req_name in REQ_CANDIDATES:
        req_file = root / req_name
        if req_file.exists():
            requirements_deps.extend(_parse_requirements(str(req_file)))

    # 合并 dedup
    seen = set()
    merged = []
    for d in ast_deps:
        if d['name'] not in seen:
            seen.add(d['name'])
            merged.append(d)
    for dep in pyproject_deps:
        pkg_name = _clean_pkg_name(dep)
        if pkg_name and pkg_name not in seen:
            seen.add(pkg_name)
            merged.append({'name': pkg_name, 'count': 0})
    for dep in requirements_deps:
        pkg_name = _clean_pkg_name(dep)
        if pkg_name and pkg_name not in seen:
            seen.add(pkg_name)
            merged.append({'name': pkg_name, 'count': 0})

    return {
        'ast': ast_deps,
        'pyproject': pyproject_deps,
        'requirements': requirements_deps,
        'merged': merged,
    }


def _run_a_route(root: Path) -> dict | None:
    """A 路：尝试 pipreqs / deptry CLI，失败返回 None"""
    pipreqs_path = shutil.which('pipreqs')
    deptry_path = shutil.which('deptry')

    if not pipreqs_path and not deptry_path:
        print("[deps] pipreqs 和 deptry 均不可用，回退 B 路", file=sys.stderr)
        return None

    result = {}

    if pipreqs_path:
        try:
            r = subprocess.run(
                [pipreqs_path, str(root), '--mode', 'no-pin', '--print'],
                capture_output=True, text=True, timeout=30,
            )
            if r.returncode == 0:
                pkgs = [p.strip() for p in r.stdout.strip().split('\n') if p.strip()]
                result['pipreqs'] = pkgs
            else:
                print(f"[deps] pipreqs 出错: {r.stderr.strip()}", file=sys.stderr)
        except Exception as e:
            print(f"[deps] pipreqs 执行失败: {e}", file=sys.stderr)

    if deptry_path:
        try:
            r = subprocess.run(
                [deptry_path, str(root)],
                capture_output=True, text=True, timeout=30,
            )
            if r.returncode == 0:
                lines = [l.strip() for l in r.stdout.strip().split('\n') if l.strip()]
                result['deptry'] = lines
        except Exception as e:
            print(f"[deps] deptry 执行失败: {e}", file=sys.stderr)

    return result if result else None


def run(root_dir: str) -> dict:
    """双路径依赖提取。

    Args:
        root_dir: 项目根目录路径

    Returns:
        dict: 包含 source, deps, pyproject_deps, requirements_deps, ast_deps 等字段
    """
    root = Path(root_dir)

    # B 路始终运行（作为底线）
    b_result = _run_b_route(root)

    # A 路可选运行（仅当 pipreqs/deptry 可用时）
    a_result = _run_a_route(root)

    if a_result:
        deps = a_result.get('pipreqs', [])
        return {
            'source': 'a_route',
            'deps': [{'name': d, 'count': 0} for d in deps],
            'pyproject_deps': b_result['pyproject'],
            'requirements_deps': b_result['requirements'],
            'ast_deps': b_result['ast'],
            'a_route_detail': a_result,
            'b_route_detail': b_result,
        }

    return {
        'source': 'b_route',
        'deps': b_result['merged'],
        'pyproject_deps': b_result['pyproject'],
        'requirements_deps': b_result['requirements'],
        'ast_deps': b_result['ast'],
        'a_route_detail': None,
        'b_route_detail': b_result,
    }


def format_plain(data: dict) -> str:
    """兼容新旧两种输出结构（v0.4.1 的旧字段 + v0.5.0 的新结构）"""
    lines = []

    # — v0.5.0 新结构 —
    deps = data.get('deps', [])
    source = data.get('source', '')
    pyproject = data.get('pyproject_deps', [])
    reqs = data.get('requirements_deps', [])
    ast_deps = data.get('ast_deps', [])
    a_detail = data.get('a_route_detail')
    b_detail = data.get('b_route_detail')

    # — v0.4.1 旧结构兼容 —
    install = data.get('install_scripts', [])

    # 检测是否为旧结构：无 source 或 deps 为空且有 install_scripts
    is_old_style = bool(install) or (not source and not deps and (pyproject or reqs))

    if is_old_style:
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

    # v0.5.0 新结构
    source_label = 'A 路（pipreqs/deptry）' if source == 'a_route' else 'B 路（AST + 映射表）'
    lines.append(f"依赖来源: {source_label}")

    if deps:
        lines.append(f"\n依赖 ({len(deps)} 项):")
        for d in deps:
            name = d['name'] if isinstance(d, dict) else d
            count = d.get('count', 0) if isinstance(d, dict) else 0
            if count:
                lines.append(f"  \u2022 {name} (引用 {count} 次)")
            else:
                lines.append(f"  \u2022 {name}")

    if ast_deps and source == 'b_route':
        lines.append(f"\nAST 扫描发现 ({len(ast_deps)} 项):")
        for d in ast_deps:
            lines.append(f"  \u2022 {d['name']} (引用 {d['count']} 次)")

    if pyproject:
        lines.append(f"\npyproject.toml 声明 ({len(pyproject)} 项):")
        for d in sorted(pyproject):
            lines.append(f"  \u2022 {d}")

    if reqs:
        lines.append(f"\nrequirements 文件 ({len(reqs)} 项):")
        for d in sorted(reqs):
            lines.append(f"  \u2022 {d}")

    if a_detail:
        if a_detail.get('pipreqs'):
            lines.append(f"\npipreqs 检测 ({len(a_detail['pipreqs'])} 项):")
            for d in sorted(a_detail['pipreqs']):
                lines.append(f"  \u2022 {d}")
        if a_detail.get('deptry'):
            if isinstance(a_detail['deptry'], list):
                lines.append(f"\ndeptry 检测 ({len(a_detail['deptry'])} 项):")
                for d in sorted(a_detail['deptry']):
                    lines.append(f"  \u2022 {d}")

    return '\n'.join(lines)
