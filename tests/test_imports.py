"""imports 提取器测试（v0.5.0 AST 版）

测试对象：scan_imports / scan_imports_full
覆盖旧正则版本的所有盲区。
"""
from pathlib import Path

import pytest

from extractors.imports import scan_imports, scan_imports_full


# ============ scan_imports_full 测试 ============


def test_full_import_os_sys(tmp_path: Path):
    """import os, sys → 两个都抓到"""
    f = tmp_path / "demo.py"
    f.write_text("import os, sys\n", encoding="utf-8")
    assert scan_imports_full(str(f)) == {"os", "sys"}


def test_full_from_multi_bracket(tmp_path: Path):
    """from foo import (a, b, c) → 正确解析括号"""
    f = tmp_path / "demo.py"
    f.write_text("from foo import (a, b, c)\n")
    assert scan_imports_full(str(f)) == {"foo"}


def test_full_multi_line_bracket(tmp_path: Path):
    """from foo import (a,b,c) 无空格 → 正确"""
    f = tmp_path / "demo.py"
    f.write_text("from foo import (a,b,c)\n")
    assert scan_imports_full(str(f)) == {"foo"}


def test_full_docstring_import_ignored(tmp_path: Path):
    """docstring 中的 import 不被提取"""
    f = tmp_path / "demo.py"
    f.write_text(
        '''"""
import os  # 这一行在 docstring 里
"""
import sys
'''
    )
    assert scan_imports_full(str(f)) == {"sys"}


def test_full_multiline_docstring_after(tmp_path: Path):
    """多行 docstring 后的 import 正常提取"""
    f = tmp_path / "demo.py"
    f.write_text(
        '''"""
这是一个多行文档字符串
它包含多行文本
"""
import json

def func():
    """函数内的文档字符串"""
    pass
'''
    )
    assert scan_imports_full(str(f)) == {"json"}


def test_full_import_as_keeps_original(tmp_path: Path):
    """import x as y → 只抓 x（原名）"""
    f = tmp_path / "demo.py"
    f.write_text("import numpy as np\n")
    assert scan_imports_full(str(f)) == {"numpy"}


def test_full_from_as_keeps_module(tmp_path: Path):
    """from x import y as z → 抓 x（模块名）"""
    f = tmp_path / "demo.py"
    f.write_text("from pathlib import Path as P\n")
    assert scan_imports_full(str(f)) == {"pathlib"}


def test_full_relative_import_dot(tmp_path: Path):
    """from . import bar → 不抓（相对 import）"""
    f = tmp_path / "demo.py"
    f.write_text("from . import bar\n")
    assert scan_imports_full(str(f)) == set()


def test_full_relative_import_dot_dot(tmp_path: Path):
    """from ..parent import child → 不抓"""
    f = tmp_path / "demo.py"
    f.write_text("from ..parent import child\n")
    assert scan_imports_full(str(f)) == set()


def test_full_relative_import_submodule(tmp_path: Path):
    """from .sub import something → 不抓"""
    f = tmp_path / "demo.py"
    f.write_text("from .sub import something\n")
    assert scan_imports_full(str(f)) == set()


def test_full_empty_file(tmp_path: Path):
    """空文件 → 空集合"""
    f = tmp_path / "empty.py"
    f.write_text("")
    assert scan_imports_full(str(f)) == set()


def test_full_comment_only(tmp_path: Path):
    """纯注释文件 → 空集合"""
    f = tmp_path / "comment.py"
    f.write_text("# 这只是注释\n# 没有 import\n")
    assert scan_imports_full(str(f)) == set()


def test_full_syntax_error(tmp_path: Path):
    """语法错误文件 → 空集合（降级，不抛异常）"""
    f = tmp_path / "broken.py"
    f.write_text("def foo(:\n")
    assert scan_imports_full(str(f)) == set()


def test_full_future_filtered(tmp_path: Path):
    """from __future__ import annotations → 被过滤"""
    f = tmp_path / "demo.py"
    f.write_text("from __future__ import annotations\nimport json\n")
    assert scan_imports_full(str(f)) == {"json"}


def test_full_future_only(tmp_path: Path):
    """只有 __future__ import → 空集合"""
    f = tmp_path / "demo.py"
    f.write_text("from __future__ import annotations\n")
    assert scan_imports_full(str(f)) == set()


def test_full_dotted_import(tmp_path: Path):
    """import os.path → 完整路径保留"""
    f = tmp_path / "demo.py"
    f.write_text("import os.path\n")
    assert scan_imports_full(str(f)) == {"os.path"}


def test_full_dotted_from_import(tmp_path: Path):
    """from collections.abc import Iterable → 完整模块路径"""
    f = tmp_path / "demo.py"
    f.write_text("from collections.abc import Iterable\n")
    assert scan_imports_full(str(f)) == {"collections.abc"}


# ============ scan_imports 测试 ============


def test_root_import_os_sys(tmp_path: Path):
    """import os, sys → 两个根名"""
    f = tmp_path / "demo.py"
    f.write_text("import os, sys\n")
    assert scan_imports(str(f)) == {"os", "sys"}


def test_root_dotted_import(tmp_path: Path):
    """import os.path → 截断为 os"""
    f = tmp_path / "demo.py"
    f.write_text("import os.path\n")
    assert scan_imports(str(f)) == {"os"}


def test_root_future_filtered(tmp_path: Path):
    """__future__ import 被过滤"""
    f = tmp_path / "demo.py"
    f.write_text("from __future__ import annotations\nimport json\n")
    assert scan_imports(str(f)) == {"json"}


def test_root_relative_ignored(tmp_path: Path):
    """相对 import 在 scan_imports 中也不出现"""
    f = tmp_path / "demo.py"
    f.write_text("from . import bar\nimport sys\n")
    assert scan_imports(str(f)) == {"sys"}
