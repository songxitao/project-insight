"""deps 双路径提取器测试（v0.5.0）"""
from pathlib import Path
from conftest import make_file
from extractors.deps import run, format_plain


def test_b_route_pyproject(tmp_project):
    """B 路: pyproject.toml 带依赖 → 正确提取"""
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
    make_file(tmp_project, "main.py", "import requests\n")
    result = run(str(tmp_project))
    assert "requests>=2.28.0" in result["pyproject_deps"]
    assert "click" in result["pyproject_deps"]
    assert "pydantic>=2.0" in result["pyproject_deps"]
    # 格式输出兼容
    plain = format_plain(result)
    assert isinstance(plain, str)
    assert "requests" in plain


def test_b_route_requirements(tmp_project):
    """B 路: requirements.txt 带依赖 → 正确提取"""
    make_file(tmp_project, "requirements.txt", "flask==2.3.0\npandas>=1.5.0\n")
    make_file(tmp_project, "main.py", "import flask\nimport pandas\n")
    result = run(str(tmp_project))
    assert "flask" in result["requirements_deps"]
    assert "pandas" in result["requirements_deps"]


def test_b_route_stdlib_filtered(tmp_project):
    """B 路: os/sys/json 等标准库不出现"""
    make_file(tmp_project, "main.py", "import os\nimport sys\nimport json\nimport re\nimport math\n")
    result = run(str(tmp_project))
    ast_deps = result.get("ast_deps", [])
    ast_names = {d["name"] for d in ast_deps}
    assert "os" not in ast_names
    assert "sys" not in ast_names
    assert "json" not in ast_names
    assert "re" not in ast_names
    assert "math" not in ast_names


def test_b_route_mapping(tmp_project):
    """B 路: cv2 → opencv-python, PIL → Pillow 等映射正确"""
    make_file(tmp_project, "img.py", "import cv2\nfrom PIL import Image\n")
    result = run(str(tmp_project))
    ast_deps = {d["name"]: d for d in result.get("ast_deps", [])}
    assert "opencv-python" in ast_deps
    assert "Pillow" in ast_deps


def test_b_route_multi_requirements(tmp_project):
    """B 路: 多个 requirements 文件合并"""
    make_file(tmp_project, "requirements.txt", "flask==2.3.0\n")
    make_file(tmp_project, "requirements-dev.txt", "pytest>=7.0\n")
    make_file(tmp_project, "main.py", "")
    result = run(str(tmp_project))
    assert "flask" in result["requirements_deps"]
    assert "pytest" in result["requirements_deps"]
    assert len(result["requirements_deps"]) == 2


def test_b_route_empty_project(tmp_project):
    """B 路: 空项目 → 空结果"""
    result = run(str(tmp_project))
    assert result.get("source") == "b_route"
    assert len(result.get("deps", [])) == 0
    assert len(result.get("pyproject_deps", [])) == 0
    assert len(result.get("requirements_deps", [])) == 0
    assert len(result.get("ast_deps", [])) == 0


def test_b_route_format_plain(tmp_project):
    """B 路: format_plain() 无异常"""
    make_file(tmp_project, "main.py", "import requests\nimport numpy\n")
    result = run(str(tmp_project))
    plain = format_plain(result)
    assert isinstance(plain, str)
    assert len(plain) > 0


def test_b_route_pipreqs_unavailable(tmp_project):
    """B 路: pipreqs 不可用时 → stderr 提示 + 返回 B 路"""
    make_file(tmp_project, "main.py", "import requests\nimport numpy\n")
    result = run(str(tmp_project))
    # CI 环境无 pipreqs/deptry → 默认回退 B 路
    assert result.get("source") == "b_route"
    assert len(result.get("deps", [])) > 0
    deps_names = {d["name"] for d in result["deps"]}
    assert "requests" in deps_names
    assert "numpy" in deps_names


def test_b_route_format_plain_old_structure(tmp_project):
    """format_plain() 兼容 v0.4.1 旧结构"""
    old_data = {
        "pyproject_deps": ["requests>=2.28.0", "click"],
        "requirements_deps": ["flask", "pandas"],
        "install_scripts": [
            {"file": "install.bat", "packages": ["numpy"]}
        ],
    }
    plain = format_plain(old_data)
    assert isinstance(plain, str)
    assert "requests" in plain
    assert "flask" in plain
    assert "numpy" in plain
