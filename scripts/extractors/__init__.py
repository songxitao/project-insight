# extractors package — 共享基础设施

"""
共享基础设施层。

提供文件遍历、目录跳过、安全读取、扩展名判断等公共工具，
以及 extractor 模块的自动注册机制。
"""

from pathlib import Path
from typing import Iterator

SKIP_DIRS = frozenset({
    '__pycache__', '.git', 'venv', '.venv', 'env',
    'node_modules', 'build', 'dist', '.pytest_cache',
    '.ruff_cache', '.workbuddy', 'output', 'outputs',
    'testset', 'model', 'models', 'checkpoints',
    '.pilot_venv', '.superpowers', '.agents', '.claude',
    '.scratch', '.egg-info', 'site-packages',
})


def should_skip(rel_path: Path) -> bool:
    """检查相对路径的任意部分是否在 SKIP_DIRS 中"""
    return any(part in SKIP_DIRS for part in rel_path.parts)


def iter_project_files(root: Path, extensions: tuple = ('.py',), key: str | None = None) -> Iterator[Path]:
    """遍历项目文件，跳过 SKIP_DIRS 目录，按扩展名白名单过滤。

    Yields 相对于 root 的路径（相对路径策略），调用方自行拼接 root。
    """
    for f in sorted(root.rglob('*')):
        if not f.is_file():
            continue
        rel = f.relative_to(root)
        if should_skip(rel):
            continue
        if extensions and f.suffix.lower() not in extensions:
            continue
        yield rel


def safe_read(filepath: Path | str, encoding: str = 'utf-8') -> str:
    """安全读取文件内容，出错返回空字符串"""
    try:
        return Path(filepath).read_text(encoding=encoding, errors='replace')
    except Exception:
        return ''


# 自动注册 — pkgutil 扫描 extractors/ 下所有带 run() 的模块
import importlib
import pkgutil
import sys

REGISTRY: dict[str, dict] = {}
for _finder, name, _ispkg in pkgutil.iter_modules(__path__):
    try:
        mod = importlib.import_module(f".{name}", __package__)
        if hasattr(mod, 'run'):
            REGISTRY[name] = {'run': mod.run, 'mod': mod}
    except Exception as e:
        print(f"[WARN] extractor '{name}' 模块加载失败: {e}", file=sys.stderr)

# 扩展注册 — patterns.py 中坍缩的 extractor 通过 EXTRA_REGISTRY 注册
try:
    from . import patterns as _patterns_mod
    if hasattr(_patterns_mod, 'EXTRA_REGISTRY'):
        REGISTRY.update(_patterns_mod.EXTRA_REGISTRY)
except Exception as e:
    print(f"[WARN] patterns.py EXTRA_REGISTRY 加载失败: {e}", file=sys.stderr)
