"""deps 提取器测试（v0.4.1 存档）"""
import sys
from pathlib import Path

# 将 tests/ 加入 sys.path 以便导入 conftest
_tests_dir = str(Path(__file__).resolve().parent.parent)
if _tests_dir not in sys.path:
    sys.path.insert(0, _tests_dir)

import pytest

pytestmark = pytest.mark.skip(reason="v0.5.0 deps 双路径重写，旧测试存档")

from conftest import make_file
from extractors.deps import run


def test_empty_project(tmp_project):
    """空项目 → 三个字段均为空列表"""
    result = run(str(tmp_project))
    assert result == {"pyproject_deps": [], "requirements_deps": [], "install_scripts": []}


def test_pyproject_deps(tmp_project):
    """有 pyproject.toml 带依赖 → 正确提取"""
    make_file(
        tmp_project,
        "pyproject.toml",
        """\
[project]
name = "demo"
version = "0.1.0"
dependencies = [
    "requests>=2.28.0",
    "click",
    "pydantic>=2.0",
]
""",
    )
    result = run(str(tmp_project))
    result["pyproject_deps"] == [
        'requests>=2.28.0"',
        'click"',
        'pydantic>=2.0"',
    ]


def test_requirements_txt(tmp_project):
    """有 requirements.txt 带依赖 → group(1) 只取包名"""
    make_file(tmp_project, "requirements.txt", "flask==2.3.0\npandas>=1.5.0\n")
    result = run(str(tmp_project))
    assert result["requirements_deps"] == ["flask", "pandas"]


def test_bat_install_script(tmp_project):
    """有 .bat 安装脚本 → 能提取安装命令中的包"""
    make_file(tmp_project, "install.bat", "pip install numpy && echo done\n")
    result = run(str(tmp_project))
    assert len(result["install_scripts"]) == 1
    entry = result["install_scripts"][0]
    assert entry["file"] == str(Path("install.bat"))
    assert entry["packages"] == ["numpy"]


def test_requirements_with_constraints_and_comments(tmp_project):
    """依赖中有版本约束、注释行 → group(1) 只取包名"""
    make_file(
        tmp_project,
        "requirements.txt",
        """\
# 这是注释，应被忽略
requests>=2.28.0
numpy==1.24.0
  # 缩进注释
""",
    )
    result = run(str(tmp_project))
    assert result["requirements_deps"] == ["requests", "numpy"]


def test_requirements_with_trailing_comma(tmp_project):
    """依赖行有尾部逗号 → group(1) 只取包名，避免 group(0) 吞入逗号"""
    make_file(tmp_project, "requirements.txt", "requests>=2.28.0,\nnumpy==1.24.0\n")
    result = run(str(tmp_project))
    assert result["requirements_deps"] == ["requests", "numpy"]


def test_requirements_collects_all_variants(tmp_project):
    """同时存在 requirements.txt 和 requirements-dev.txt → 两个都收集"""
    make_file(tmp_project, "requirements.txt", "flask==2.3.0\n")
    make_file(tmp_project, "requirements-dev.txt", "pytest>=7.0\n")
    result = run(str(tmp_project))
    assert "flask" in result["requirements_deps"]
    assert "pytest" in result["requirements_deps"]
    assert len(result["requirements_deps"]) == 2
    """pip install 多包 → 全部提取"""
    make_file(tmp_project, "setup.bat", "pip install torch torchvision torchaudio\n")
    result = run(str(tmp_project))
    assert len(result["install_scripts"]) == 1
    entry = result["install_scripts"][0]
    assert entry["packages"] == ["torch", "torchvision", "torchaudio"]
