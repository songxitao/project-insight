"""
项目骨架树模块 — 递归扫描目录，生成过滤后的树结构。

核心设计原则：
  本项目只读代码文本文件，非代码内容（二进制、模型权重、媒体、数据）不读、不解析。
  尺度保护策略：
    - SKIP_DIRS 跳过已知非代码目录（model/、outputs/、venv/ 等）
    - BINARY_EXTS 跳过已知二进制扩展名（_count_lines 中行数记 0，但保留路径和大小信息）
    - MAX_LINES_READ_MB = 50MB 硬上限，任何超过此大小的文件不读内容

用法:
    from extractors.tree import run
    result = run("/path/to/project")
"""

from pathlib import Path

from . import SKIP_DIRS as _BASE_SKIP_DIRS


SKIP_DIRS = _BASE_SKIP_DIRS | {'__init__.py'}

# 已知二进制/模型文件扩展名 — 跳过行数统计
BINARY_EXTS = frozenset({
    '.safetensors', '.bin', '.pt', '.pth', '.ckpt', '.onnx',
    '.h5', '.pkl', '.joblib', '.gguf', '.ggml', '.npy',
    '.npz', '.arrow', '.parquet', '.so', '.dll', '.pyd',
    '.pyc', '.pyo', '.db', '.sqlite', '.sqlite3', '.jpg',
    '.jpeg', '.png', '.gif', '.bmp', '.webp', '.mp4',
    '.mp3', '.wav', '.flac', '.avi', '.mov', '.mkv',
})

# 超过此大小的文件跳过行数统计（避免读取大体积模型/数据文件）
MAX_LINES_READ_MB = 50


def _count_lines(filepath: str) -> int:
    """简单行数计数（仅对文本文件，跳过二进制和大文件）"""
    try:
        fpath = Path(filepath)
        # 按扩展名跳过已知二进制格式
        if fpath.suffix.lower() in BINARY_EXTS:
            return 0
        # 按文件大小跳过大型文件
        if fpath.stat().st_size > MAX_LINES_READ_MB * 1024 * 1024:
            return 0
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


def format_plain(data: dict) -> str:
    """将树数据格式化为可读文本"""
    def _append_tree(node, lines: list, indent: int = 0):
        if node is None:
            return
        prefix = '  ' * indent
        if 'children' in node:
            lines.append(f"{prefix}📁 {node['path']}/")
            for child in node.get('children', []):
                _append_tree(child, lines, indent + 1)
        else:
            tag = node.get('tag', '')
            size = node.get('size_kb', 0)
            lines_count = node.get('lines', 0)
            tag_str = f" {tag}" if tag else ""
            lines.append(f"{prefix}📄 {node['path']}{tag_str}  ({size} KB, {lines_count} 行)")

    tree = data.get('project_tree')
    if tree is None:
        return ''
    lines = ["\n🌳 项目骨架树:"]
    _append_tree(tree, lines, indent=2)
    return '\n'.join(lines)
