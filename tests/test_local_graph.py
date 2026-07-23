"""
Tests for local_graph.py — local module dependency graph.
"""
from extractors.local_graph import run


def test_empty_project(tmp_project):
    """空项目 → 空依赖图 + 空断裂引用"""
    result = run(str(tmp_project))
    assert result["local_dep_graph"] == {}
    assert result["broken_imports"] == {}


def test_single_file_no_imports(tmp_project):
    """单文件无 import → 空图"""
    (tmp_project / "main.py").write_text("x = 42\n", encoding="utf-8")
    result = run(str(tmp_project))
    assert result["local_dep_graph"] == {}
    assert result["broken_imports"] == {}


def test_cross_file_import_creates_edge(tmp_project):
    """一个模块 import 另一个 → 建立依赖"""
    (tmp_project / "utils.py").write_text("def helper(): pass\n", encoding="utf-8")
    (tmp_project / "main.py").write_text("import utils\n", encoding="utf-8")
    result = run(str(tmp_project))
    assert result["local_dep_graph"] == {"main.py": ["utils"]}


def test_multiple_dependencies(tmp_project):
    """多个 import 均正确解析为本地模块"""
    (tmp_project / "a.py").write_text("import b\nimport c\n", encoding="utf-8")
    (tmp_project / "b.py").write_text("x = 1\n", encoding="utf-8")
    (tmp_project / "c.py").write_text("y = 2\n", encoding="utf-8")
    result = run(str(tmp_project))
    assert result["local_dep_graph"]["a.py"] == ["b", "c"]


def test_package_with_init(tmp_project):
    """__init__.py 使目录成为可识别的包模块"""
    pkg = tmp_project / "mypkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    (tmp_project / "app.py").write_text("import mypkg\n", encoding="utf-8")
    result = run(str(tmp_project))
    assert result["local_dep_graph"] == {"app.py": ["mypkg"]}


def test_skip_dirs_ignored(tmp_project):
    """跳过目录中的 .py 文件不参与依赖图"""
    skip_dir = tmp_project / ".venv" / "lib"
    skip_dir.mkdir(parents=True)
    (skip_dir / "site.py").write_text("import os\n", encoding="utf-8")
    (tmp_project / "main.py").write_text("x = 1\n", encoding="utf-8")
    result = run(str(tmp_project))
    assert result["local_dep_graph"] == {}
    assert result["broken_imports"] == {}


def test_external_imports_omitted(tmp_project):
    """标准库/第三方 import 不进入本地依赖图"""
    (tmp_project / "main.py").write_text(
        "import os\nimport sys\n", encoding="utf-8"
    )
    result = run(str(tmp_project))
    assert result["local_dep_graph"] == {}
    assert result["broken_imports"] == {}


def test_normal_imports_still_work(tmp_project):
    """正常引用（目标文件存在）→ 结果不变（兼容）"""
    (tmp_project / "utils.py").write_text("def helper(): pass\n", encoding="utf-8")
    (tmp_project / "main.py").write_text("import utils\n", encoding="utf-8")
    result = run(str(tmp_project))
    assert result["local_dep_graph"] == {"main.py": ["utils"]}
    assert result["broken_imports"] == {}


def test_broken_import_package_without_init(tmp_project):
    """父包没有 __init__.py，import 父包 → broken_imports"""
    pkg = tmp_project / "subpkg"
    pkg.mkdir()
    (pkg / "a.py").write_text("x = 1\n", encoding="utf-8")
    (tmp_project / "main.py").write_text("import subpkg\n", encoding="utf-8")
    result = run(str(tmp_project))
    assert result["local_dep_graph"] == {}
    assert result["broken_imports"] == {"main.py": ["subpkg"]}


def test_mixed_broken_and_valid_imports(tmp_project):
    """混合场景：部分引用存在 + 部分断裂"""
    # utils.py 存在 → 正常引用
    (tmp_project / "utils.py").write_text("def h(): pass\n", encoding="utf-8")
    # mypkg 有子模块但无 __init__.py → 断裂引用
    pkg = tmp_project / "mypkg"
    pkg.mkdir()
    (pkg / "a.py").write_text("x = 1\n", encoding="utf-8")
    (tmp_project / "main.py").write_text(
        "import utils\nimport mypkg\n", encoding="utf-8"
    )
    result = run(str(tmp_project))
    assert result["local_dep_graph"] == {"main.py": ["utils"]}
    assert result["broken_imports"] == {"main.py": ["mypkg"]}


def test_empty_project_no_error(tmp_project):
    """空项目 → 不报错，返回空字段"""
    result = run(str(tmp_project))
    assert result["local_dep_graph"] == {}
    assert result["broken_imports"] == {}
