"""
pytest 共享配置

- 将 scripts/ 加入 sys.path，使测试能 from extractors import xxx
- 提供 tmp_project fixture：创建临时项目目录 + 测试文件生命周期管理
"""

import os
import shutil
import sys
import tempfile
from pathlib import Path

import pytest

# 将项目 scripts 目录加入模块搜索路径
SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))


@pytest.fixture
def tmp_project():
    """创建一个临时项目目录，测试完自动清理。

    返回 Path 对象，指向临时目录根。
    """
    tmpdir = Path(tempfile.mkdtemp(prefix="project_insight_test_"))
    yield tmpdir
    shutil.rmtree(tmpdir, ignore_errors=True)


def make_file(base: Path, rel_path: str, content: str = ""):
    """在 base 目录下创建文件（自动创建父目录）。"""
    target = base / rel_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return target
