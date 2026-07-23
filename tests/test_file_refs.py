"""file_refs 提取器测试"""
from pathlib import Path
from conftest import make_file
from extractors.file_refs import run, format_plain


def test_empty_project(tmp_project):
    """空项目 -> 空结果"""
    result = run(str(tmp_project))
    assert result == {"file_refs": []}


def test_path_call_with_existing_file(tmp_project):
    """Path("app_control.py") 且文件存在 -> exists: true"""
    make_file(tmp_project, "app_control.py", "print('ok')")
    make_file(tmp_project, "main.py", 'Path("app_control.py")\n')
    result = run(str(tmp_project))
    assert len(result["file_refs"]) == 1
    entry = result["file_refs"][0]
    assert entry["ref"] == "app_control.py"
    assert entry["type"] == "Path()"
    assert entry["exists"] is True


def test_path_call_with_missing_file(tmp_project):
    """Path("missing.py") 文件不存在 -> exists: false"""
    make_file(tmp_project, "main.py", 'Path("missing.py")\n')
    result = run(str(tmp_project))
    assert len(result["file_refs"]) == 1
    entry = result["file_refs"][0]
    assert entry["ref"] == "missing.py"
    assert entry["type"] == "Path()"
    assert entry["exists"] is False


def test_open_call(tmp_project):
    """open("data.json") 匹配"""
    make_file(tmp_project, "data.json", '{"key": "val"}')
    make_file(tmp_project, "loader.py", 'open("data.json")\n')
    result = run(str(tmp_project))
    assert len(result["file_refs"]) == 1
    entry = result["file_refs"][0]
    assert entry["ref"] == "data.json"
    assert entry["type"] == "open()"
    assert entry["exists"] is True


def test_subprocess_script_ref(tmp_project):
    """subprocess.Popen(["python", "script.py"]) 匹配脚本引用"""
    make_file(tmp_project, "script.py", "print('hi')")
    make_file(tmp_project, "runner.py",
              'subprocess.Popen(["python", "script.py"])\n')
    result = run(str(tmp_project))
    assert len(result["file_refs"]) == 1
    entry = result["file_refs"][0]
    assert entry["ref"] == "script.py"
    assert entry["type"] == "subprocess"
    assert entry["exists"] is True


def test_bare_string_no_extension(tmp_project):
    """裸字符串无扩展名 -> 不报"""
    make_file(tmp_project, "config.py", 'some_var = "some_string"\n')
    result = run(str(tmp_project))
    assert result == {"file_refs": []}


def test_skip_dir_not_scanned(tmp_project):
    """跳过目录中的文件不扫描"""
    make_file(tmp_project,
              ".venv/lib/site-packages/pkg.py",
              'Path("internal.py")\n')
    result = run(str(tmp_project))
    assert result == {"file_refs": []}


def test_format_plain_no_error(tmp_project):
    """format_plain() 正常输出不抛出异常"""
    make_file(tmp_project, "app_control.py", "print('ok')")
    make_file(tmp_project, "main.py", 'Path("app_control.py")\n')
    result = run(str(tmp_project))
    text = format_plain(result)
    assert isinstance(text, str)
    assert "app_control.py" in text


def test_line_number_correct(tmp_project):
    """行号提取正确"""
    make_file(tmp_project, "app.py", "x = 1\n")
    make_file(tmp_project, "main.py",
              "import os\n"
              'Path("app.py")\n'
              "print('done')\n")
    result = run(str(tmp_project))
    assert len(result["file_refs"]) == 1
    assert result["file_refs"][0]["line"] == 2


def test_single_quote_path(tmp_project):
    """Path('xx.py') 单引号也匹配"""
    make_file(tmp_project, "util.py", "print('ok')")
    make_file(tmp_project, "main.py", "Path('util.py')\n")
    result = run(str(tmp_project))
    assert len(result["file_refs"]) == 1
    assert result["file_refs"][0]["ref"] == "util.py"


def test_format_plain_empty(tmp_project):
    """空结果调用 format_plain -> 空字符串"""
    result = run(str(tmp_project))
    assert format_plain(result) == ""
