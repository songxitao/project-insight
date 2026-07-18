"""imports 提取器测试"""
from pathlib import Path
from conftest import make_file
from extractors.imports import run


def test_empty_project(tmp_project):
    """空项目 → {'source_imports': {}}"""
    result = run(str(tmp_project))
    assert result == {"source_imports": {}}


def test_import_statement(tmp_project):
    """有 .py 文件含 import 语句 → 正确提取"""
    make_file(tmp_project, "main.py", "import os\nimport sys\n")
    result = run(str(tmp_project))
    assert result["source_imports"]["main.py"] == ["os", "sys"]


def test_from_import_statement(tmp_project):
    """有 from ... import 语句 → 正确提取"""
    make_file(tmp_project, "utils.py", "from pathlib import Path\nfrom collections.abc import Iterable\n")
    result = run(str(tmp_project))
    assert result["source_imports"]["utils.py"] == ["collections", "pathlib"]


def test_docstring_import_ignored(tmp_project):
    """文档字符串中的 import 不被提取"""
    make_file(
        tmp_project,
        "demo.py",
        '''"""
模块文档字符串。
import os  # 这一行不应被提取
"""
import sys
''',
    )
    result = run(str(tmp_project))
    assert result["source_imports"]["demo.py"] == ["sys"]


def test_inside_def_ignored(tmp_project):
    """函数体内部的 import 不被提取（遇到 def 就停）"""
    make_file(
        tmp_project,
        "app.py",
        """import os

def my_func():
    import sys
    from pathlib import Path
""",
    )
    result = run(str(tmp_project))
    assert result["source_imports"]["app.py"] == ["os"]


def test_future_import_filtered(tmp_project):
    """__future__ import 被过滤"""
    make_file(
        tmp_project,
        "main.py",
        "from __future__ import annotations\nimport json\n",
    )
    result = run(str(tmp_project))
    assert result["source_imports"]["main.py"] == ["json"]


def test_skip_dir_ignored(tmp_project):
    """__pycache__ 等跳过目录中的 .py 被忽略"""
    make_file(tmp_project, "__pycache__/cached.py", "import os\n")
    make_file(tmp_project, "venv/lib/main.py", "import sys\n")
    result = run(str(tmp_project))
    assert result["source_imports"] == {}
