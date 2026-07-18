"""测试 project_insight_v1.py 遗留版本"""

import sys
from pathlib import Path

import pytest

from project_insight_v1 import main as v1_main


def test_main_basic(monkeypatch, capsys):
    """main() 基本调用（默认当前目录）应产生输出"""
    monkeypatch.setattr(sys, 'argv', ['prog'])
    v1_main()
    captured = capsys.readouterr()
    assert '项目依赖摘要' in captured.out


def test_main_with_path(tmp_project, monkeypatch, capsys):
    """main() 指定临时目录应成功执行"""
    # 在临时项目中创建文件以触发提取逻辑
    (tmp_project / "hello.py").write_text("import os\nimport sys\n", encoding="utf-8")
    monkeypatch.setattr(sys, 'argv', ['prog', str(tmp_project)])
    v1_main()
    captured = capsys.readouterr()
    assert '项目依赖摘要' in captured.out
    assert 'hello.py' in captured.out
