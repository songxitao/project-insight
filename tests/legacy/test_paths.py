import pytest
pytestmark = pytest.mark.skip(reason="v0.5.0 正则坍缩到 patterns.py，旧测试存档")

"""paths 提取器测试"""
from pathlib import Path
from conftest import make_file
from extractors.paths import run


def test_empty_project(tmp_project):
    """空项目 → {'local_paths': []}"""
    result = run(str(tmp_project))
    assert result == {"local_paths": []}


def test_sys_path_insert(tmp_project):
    """PYTHONPATH 赋值 → 能提取到"""
    make_file(tmp_project, "config.py", 'PYTHONPATH="C:\\\\project\\\\lib"\n')
    result = run(str(tmp_project))
    assert len(result["local_paths"]) == 1
    entry = result["local_paths"][0]
    assert entry["file"] == str(Path("config.py"))


def test_sys_path_append(tmp_project):
    """sys.path.append 带路径 → 能提取到"""
    make_file(tmp_project, "setup.py", 'sys.path.append("D:/tools/bin")\n')
    result = run(str(tmp_project))
    assert len(result["local_paths"]) == 1
    entry = result["local_paths"][0]
    assert entry["file"] == str(Path("setup.py"))
    assert entry["paths"] == ["D:/tools/bin"]


def test_no_hardcoded_path(tmp_project):
    """没有硬编码路径的文件 → 不被提取"""
    make_file(tmp_project, "main.py", "import os\nprint('hello')\n")
    result = run(str(tmp_project))
    assert result["local_paths"] == []


def test_skip_dir_ignored(tmp_project):
    """跳过目录中的文件 → 不被扫描"""
    make_file(tmp_project, ".venv/lib/site-packages/pkg.py", 'sys.path.insert(0, "C:\\secret")\n')
    make_file(tmp_project, "node_modules/lib/index.py", 'sys.path.append("D:\\hack")\n')
    result = run(str(tmp_project))
    assert result["local_paths"] == []
