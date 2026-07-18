"""
项目骨架树模块 — 递归扫描目录，生成过滤后的树结构。

用法:
    from extractors.tree import run
    result = run("/path/to/project")
"""

from pathlib import Path


SKIP_DIRS = frozenset({
    '__pycache__', '.git', 'venv', '.venv', 'env',
    'node_modules', 'build', 'dist', '.pytest_cache',
    '.ruff_cache', '.workbuddy', 'output', 'testset',
    '.pilot_venv', '.superpowers', '.agents', '.claude',
    '.scratch', '.egg-info', 'site-packages', '__init__.py',
})


def _count_lines(filepath: str) -> int:
    """简单行数计数（仅对文本文件）"""
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            return sum(1 for _ in f)
    except Exception:
        return 0


def _get_tag(filename: str) -> str | None:
    """根据文件名标注角色标签"""
    name_lower = filename.lower()
    if name_lower in ('main.py', 'app.py', 'cli.py'):
        return '[入口]'
    if filename.startswith('test_') or filename == 'conftest.py':
        return '[测试]'
    if filename in ('dockerfile', 'dockerfile.dev', 'dockerfile.prod',
                    'docker-compose.yml', 'docker-compose.yaml'):
        return '[部署]'
    if filename.endswith('.md'):
        return '[文档]'
    if filename in ('pyproject.toml', 'setup.py', 'setup.cfg') or \
       filename.startswith('requirements') and filename.endswith('.txt'):
        return '[配置]'
    return None


def _build_tree(node: Path, root: Path) -> dict | None:
    """递归构建树节点"""
    if node.name in SKIP_DIRS:
        return None

    rel = node.relative_to(root)
    rel_str = str(rel.as_posix())

    if node.is_file():
        size_kb = round(node.stat().st_size / 1024, 1)
        lines = _count_lines(str(node))
        entry = {
            'path': rel_str,
            'size_kb': size_kb,
            'lines': lines,
        }
        tag = _get_tag(node.name)
        if tag:
            entry['tag'] = tag
        return entry

    if node.is_dir():
        children = []
        for child in sorted(node.iterdir()):
            child_node = _build_tree(child, root)
            if child_node is not None:
                children.append(child_node)
        if not children:
            return None
        return {
            'path': rel_str,
            'type': 'dir',
            'children': children,
        }


def run(root_dir: str) -> dict:
    """生成项目骨架树"""
    root = Path(root_dir).resolve()
    tree = _build_tree(root, root)
    return {'project_tree': tree}
