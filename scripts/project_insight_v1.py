#!/usr/bin/env python3
"""
极简依赖提取器 — 用正则从代码中"抠"出硬依赖，不读完整文件。

用法:
  python scripts/qc_extract_deps.py [path] [--format json|plain]

输出:
  只输出正则匹配到的依赖行，不输出无关文件内容（省 token）。
"""

import argparse
import json
import os
import re
import sys
from collections import defaultdict
from pathlib import Path

# ── 四类正则模式（针对性提取，不读文件全文） ──────────────

# 1. pyproject.toml / requirements.txt 中的包名（支持 extras 语法如 uvicorn[standard]）
DEP_PATTERN = re.compile(
    r'^[\s\'"]*([a-zA-Z0-9_\-\.]+(?:\[[a-zA-Z0-9_,\-\.]+\])?)'  # 包名 + 可选 extras
    r'(?:\s*[><=!~]+\s*[\d.*,\s]+)?'                             # 可选版本号（含逗号多约束）
    r'(?:\s*[,;]|$)',                                             # 分隔或结束
    re.MULTILINE
)

# 2. Python import / from 语句（源码中的硬依赖）
IMPORT_PATTERN = re.compile(
    r'^(?:import|from)\s+([a-zA-Z0-9_\.]+)', re.MULTILINE
)

# 3. sys.path 插入 / PYTHONPATH 引用 — 本地路径硬编码
PATH_PATTERN = re.compile(
    r'(?:sys\.path\.insert|sys\.path\.append|PYTHONPATH|PATH=)'
    r'[\s\(]*[\'"]?([a-zA-Z]:[\\/][^\'")\s]+)[\'"]?',
)

# 4. Conda / pip install 行（Dockerfile, .bat, Makefile 中的）
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
    """
    从 requirements.txt 文件提取依赖（含变体：requirements-dev.txt, requirements_dev.txt）。
    每行提取包名和可选版本号，跳过注释行和 -r/-e/-- 开头的选项行。
    """
    content = Path(filepath).read_text(encoding='utf-8', errors='replace')
    deps = []
    for line in content.split('\n'):
        stripped = line.strip()
        if not stripped or stripped.startswith('#'):
            continue
        # 跳过选项行
        if stripped.startswith(('-r', '-e', '--', '-c', '-f')):
            continue
        # 剥离行内注释（# 之后的内容）
        no_comment = stripped.split(' #', 1)[0].split('\t#', 1)[0].strip()
        m = DEP_PATTERN.match(no_comment)
        if m:
            deps.append(m.group(0).strip())
    return deps


def scan_imports(filepath: str) -> set:
    """从 .py 文件提取顶层 import（不读函数体内部的 import）"""
    content = Path(filepath).read_text(encoding='utf-8')
    lines = content.split('\n')
    imports = set()
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith('#'):
            continue
        m = IMPORT_PATTERN.match(stripped)
        if m:
            root = m.group(1).split('.')[0]
            if root != '__future__':
                imports.add(root)
        if stripped.startswith(('def ', 'class ', '@')):
            break
    return imports


def scan_install_commands(filepath: str) -> list:
    """从 .bat / .sh / Dockerfile 找安装命令中的依赖"""
    content = Path(filepath).read_text(encoding='utf-8', errors='replace')
    found = []
    for m in INSTALL_PATTERN.finditer(content):
        pkgs = re.findall(r'([a-zA-Z0-9_\-\.]+(?:==[\d.*]+)?)', m.group(1))
        found.extend(pkgs)
    return found


def scan_local_paths(filepath: str) -> list:
    """从文件找硬编码的本地路径（sys.path.insert/append, PYTHONPATH, PATH=）"""
    content = Path(filepath).read_text(encoding='utf-8', errors='replace')
    return [m.group(1) for m in PATH_PATTERN.finditer(content)]


def is_script_file(f: Path) -> bool:
    """判断是否为安装脚本类文件（.bat/.sh/.ps1/Dockerfile 变体）"""
    ext = f.suffix.lower()
    if ext in ('.bat', '.sh', '.ps1'):
        return True
    if f.name.lower() in ('dockerfile', 'dockerfile.dev', 'dockerfile.prod'):
        return True
    return False


def main():
    parser = argparse.ArgumentParser(
        description='从项目代码中提取依赖、import 和本地路径硬编码',
    )
    parser.add_argument(
        'path', nargs='?', default='.',
        help='项目根目录路径（默认当前目录）',
    )
    parser.add_argument(
        '--format', choices=['json', 'plain'], default='plain',
        help='输出格式：json（结构化）或 plain（可读文本，默认）',
    )
    args = parser.parse_args()

    root_dir = args.path
    fmt = args.format

    result = {
        'pyproject_deps': [],
        'requirements_deps': [],
        'source_imports': {},
        'install_scripts': [],
        'local_paths': [],
    }

    # 只扫描关键文件（不遍历无关文件）
    for f in sorted(Path(root_dir).rglob('*')):
        if not f.is_file():
            continue
        skip_dirs = {'__pycache__', '.git', 'venv', '.venv', 'env',
                     'node_modules', 'build', 'dist', '.pytest_cache',
                     '.ruff_cache', '.workbuddy', 'output', 'testset',
                     '.pilot_venv', '.superpowers', '.agents', '.claude'}
        if any(p.name in skip_dirs for p in f.parents):
            continue

        ext = f.suffix.lower()
        if ext == '.py':
            imports = scan_imports(str(f))
            if imports:
                result['source_imports'][str(f.relative_to(root_dir))] = sorted(imports)
            # .py 文件也可能有 sys.path.insert 等本地路径硬编码
            paths = scan_local_paths(str(f))
            if paths:
                result['local_paths'].append({
                    'file': str(f.relative_to(root_dir)),
                    'paths': paths
                })
        elif is_script_file(f):
            pkgs = scan_install_commands(str(f))
            if pkgs:
                result['install_scripts'].append({
                    'file': str(f.relative_to(root_dir)),
                    'packages': pkgs
                })
            paths = scan_local_paths(str(f))
            if paths:
                result['local_paths'].append({
                    'file': str(f.relative_to(root_dir)),
                    'paths': paths
                })

    # pyproject.toml
    pyproject = Path(root_dir) / 'pyproject.toml'
    if pyproject.exists():
        result['pyproject_deps'] = scan_pyproject(str(pyproject))

    # requirements.txt 及其常见变体
    req_candidates = [
        'requirements.txt',
        'requirements-dev.txt',
        'requirements_dev.txt',
        'requirements-dev.lock',
    ]
    for req_name in req_candidates:
        req_file = Path(root_dir) / req_name
        if req_file.exists():
            result['requirements_deps'] = scan_requirements_txt(str(req_file))
            break

    # 输出
    if fmt == 'json':
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"{'='*60}")
        print(f"📦 项目依赖摘要")
        print(f"{'='*60}")
        if result['pyproject_deps']:
            print(f"\npyproject.toml 声明依赖 ({len(result['pyproject_deps'])} 项):")
            for d in sorted(result['pyproject_deps']):
                print(f"  • {d}")
        if result['requirements_deps']:
            print(f"\nrequirements.txt 声明依赖 ({len(result['requirements_deps'])} 项):")
            for d in sorted(result['requirements_deps']):
                print(f"  • {d}")
        for f, imps in sorted(result['source_imports'].items()):
            print(f"\n  {f} 用到 {len(imps)} 个包:")
            for i in sorted(imps):
                print(f"    └─ {i}")
        if result['install_scripts']:
            print(f"\n📜 安装脚本中的依赖:")
            for s in result['install_scripts']:
                print(f"  {s['file']}: {', '.join(s['packages'])}")
        if result['local_paths']:
            print(f"\n⚠️ 本地路径硬编码:")
            for s in result['local_paths']:
                for p in s['paths']:
                    print(f"  {s['file']} → {p}")


if __name__ == '__main__':
    main()
