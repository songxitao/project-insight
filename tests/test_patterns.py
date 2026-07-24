"""测试 patterns.py — urls/paths/entries/file_refs 的统一测试。"""
from pathlib import Path

from extractors.patterns import (
    run_urls, run_paths, run_entries, run_file_refs,
    format_plain, REGEX_PATTERNS, ScanPattern,
)


# ===================================================================
# urls — 硬编码端口/URL/IP
# ===================================================================

class TestUrls:
    def test_empty_project(self, tmp_project):
        result = run_urls(str(tmp_project))
        assert result["hardcoded_urls"] == []

    def test_port_assignment(self, tmp_project):
        (tmp_project / "config.yaml").write_text("port=8080\n", encoding="utf-8")
        result = run_urls(str(tmp_project))
        assert 8080 in result["hardcoded_urls"][0]["ports"]

    def test_localhost_port(self, tmp_project):
        (tmp_project / "config.yaml").write_text(
            'url = "http://localhost:3000/api"\n', encoding="utf-8"
        )
        result = run_urls(str(tmp_project))
        assert 3000 in result["hardcoded_urls"][0]["localhost_ports"]

    def test_blacklist_filtered(self, tmp_project):
        (tmp_project / "config.yaml").write_text(
            'url = "http://example.com/test"\n', encoding="utf-8"
        )
        result = run_urls(str(tmp_project))
        assert result["hardcoded_urls"] == []

    def test_custom_url_extracted(self, tmp_project):
        (tmp_project / "config.yaml").write_text(
            'url = "http://myapi.internal/v1/data"\n', encoding="utf-8"
        )
        result = run_urls(str(tmp_project))
        assert "http://myapi.internal/v1/data" in result["hardcoded_urls"][0]["urls"]

    def test_ip_address_extracted(self, tmp_project):
        (tmp_project / "config.yaml").write_text(
            'host = "192.168.1.1"\n', encoding="utf-8"
        )
        result = run_urls(str(tmp_project))
        assert "192.168.1.1" in result["hardcoded_urls"][0]["ips"]

    def test_zero_host_port(self, tmp_project):
        (tmp_project / "config.yaml").write_text(
            'bind = "0.0.0.0:5432"\n', encoding="utf-8"
        )
        result = run_urls(str(tmp_project))
        assert 5432 in result["hardcoded_urls"][0]["zero_host_ports"]

    def test_skip_dirs_ignored(self, tmp_project):
        skip_dir = tmp_project / ".venv"
        skip_dir.mkdir(parents=True)
        (skip_dir / "config.yaml").write_text("port=8080\n", encoding="utf-8")
        result = run_urls(str(tmp_project))
        assert result["hardcoded_urls"] == []

    def test_summary_dedup(self, tmp_project):
        (tmp_project / "a.yaml").write_text('host = "10.0.0.1"\n', encoding="utf-8")
        (tmp_project / "b.yaml").write_text('host = "10.0.0.1"\n', encoding="utf-8")
        result = run_urls(str(tmp_project))
        assert result["hardcoded_urls_summary"]["unique_ips"] == ["10.0.0.1"]

    def test_format_plain(self, tmp_project):
        (tmp_project / "app.yaml").write_text("port=9090\n", encoding="utf-8")
        result = run_urls(str(tmp_project))
        text = format_plain(result)
        assert "9090" in text
        assert "端口" in text


# ===================================================================
# paths — 本地硬编码路径
# ===================================================================

class TestPaths:
    def test_empty_project(self, tmp_project):
        result = run_paths(str(tmp_project))
        assert result == {"local_paths": []}

    def test_sys_path_insert(self, tmp_project):
        (tmp_project / "config.py").write_text(
            'PYTHONPATH="C:\\\\project\\\\lib"\n', encoding="utf-8"
        )
        result = run_paths(str(tmp_project))
        assert len(result["local_paths"]) == 1
        assert result["local_paths"][0]["file"] == str(Path("config.py"))

    def test_sys_path_append(self, tmp_project):
        (tmp_project / "setup.py").write_text(
            'sys.path.append("D:/tools/bin")\n', encoding="utf-8"
        )
        result = run_paths(str(tmp_project))
        assert result["local_paths"][0]["paths"] == ["D:/tools/bin"]

    def test_no_hardcoded_path(self, tmp_project):
        (tmp_project / "main.py").write_text(
            "import os\nprint('hello')\n", encoding="utf-8"
        )
        result = run_paths(str(tmp_project))
        assert result["local_paths"] == []

    def test_skip_dir_ignored(self, tmp_project):
        p = tmp_project / ".venv" / "lib" / "site-packages" / "pkg.py"
        p.parent.mkdir(parents=True)
        p.write_text('sys.path.insert(0, "C:\\secret")\n', encoding="utf-8")
        result = run_paths(str(tmp_project))
        assert result["local_paths"] == []

    def test_only_py_bat_sh_ps1_dockerfile(self, tmp_project):
        (tmp_project / "notes.txt").write_text(
            'sys.path.insert(0, "C:\\data")\n', encoding="utf-8"
        )
        result = run_paths(str(tmp_project))
        assert result["local_paths"] == []

    def test_format_plain(self, tmp_project):
        (tmp_project / "cfg.py").write_text(
            'sys.path.append("D:/tools/bin")\n', encoding="utf-8"
        )
        result = run_paths(str(tmp_project))
        text = format_plain(result)
        assert "D:/tools/bin" in text


# ===================================================================
# entries — 入口点与 API 端点
# ===================================================================

class TestEntries:
    def test_main_guard_detected(self, tmp_project):
        p = tmp_project / "main.py"
        p.write_text("if __name__ == '__main__':\n    main()\n", encoding="utf-8")
        result = run_entries(str(tmp_project))
        assert len(result["entry_points"]) == 1
        assert result["entry_points"][0]["type"] == "main_guard"

    def test_web_framework_detected(self, tmp_project):
        p = tmp_project / "app.py"
        p.write_text("from fastapi import FastAPI\napp = FastAPI()\n", encoding="utf-8")
        result = run_entries(str(tmp_project))
        types = [ep["type"] for ep in result["entry_points"]]
        assert "web_framework" in types

    def test_cli_tool_detected(self, tmp_project):
        p = tmp_project / "cli.py"
        p.write_text("@click.command()\ndef hello(): pass\n", encoding="utf-8")
        result = run_entries(str(tmp_project))
        types = [ep["type"] for ep in result["entry_points"]]
        assert "cli_tool" in types

    def test_server_launcher_detected(self, tmp_project):
        p = tmp_project / "serve.py"
        p.write_text("uvicorn.run(app, host='0.0.0.0')\n", encoding="utf-8")
        result = run_entries(str(tmp_project))
        types = [ep["type"] for ep in result["entry_points"]]
        assert "server_launcher" in types

    def test_api_route_extracted(self, tmp_project):
        p = tmp_project / "api.py"
        p.write_text("@app.get('/hello')\nasync def hello(): pass\n", encoding="utf-8")
        result = run_entries(str(tmp_project))
        assert len(result["api_endpoints"]) == 1
        assert result["api_endpoints"][0]["route"] == "/hello"

    def test_no_entry_points_returns_empty(self, tmp_project):
        p = tmp_project / "utils.py"
        p.write_text("def helper(x):\n    return x\n", encoding="utf-8")
        result = run_entries(str(tmp_project))
        assert result["entry_points"] == []

    def test_api_post_and_delete(self, tmp_project):
        p = tmp_project / "api.py"
        p.write_text(
            "@router.post('/items')\n"
            "@router.delete('/items/{id}')\n"
            "def handle(): pass\n",
            encoding="utf-8",
        )
        result = run_entries(str(tmp_project))
        routes = [ep["route"] for ep in result["api_endpoints"]]
        assert "/items" in routes
        assert "/items/{id}" in routes

    def test_long_file_snippet_only_scans_head_and_tail(self, tmp_project):
        lines = ["x = 1\n"] * 240
        lines[9] = "if __name__ == '__main__':\n"       # head → 应检测
        lines[209] = "if __name__ == '__main__':\n"     # 中间 → 不应检测
        content = "".join(lines)
        p = tmp_project / "long.py"
        p.write_text(content, encoding="utf-8")
        result = run_entries(str(tmp_project))
        assert len(result["entry_points"]) == 1
        assert result["entry_points"][0]["line"] == 10

    def test_pattern_definition_lines_not_matched(self, tmp_project):
        p = tmp_project / "fake_patterns.py"
        p.write_text(
            'import re\n'
            "ENTRY_PATTERNS = [\n"
            '    (re.compile(r"if\\s+__name__\\s*==\\s*[\'\"]__main__[\'\"]"), \'main_guard\'),\n'
            "]\n"
            "x = 42\n",
            encoding="utf-8",
        )
        result = run_entries(str(tmp_project))
        assert len(result["entry_points"]) == 0

    def test_format_plain(self, tmp_project):
        p = tmp_project / "main.py"
        p.write_text("if __name__ == '__main__':\n    main()\n", encoding="utf-8")
        result = run_entries(str(tmp_project))
        text = format_plain(result)
        assert "入口点" in text
        assert "main.py" in text


# ===================================================================
# file_refs — 文件引用
# ===================================================================

class TestFileRefs:
    def test_empty_project(self, tmp_project):
        result = run_file_refs(str(tmp_project))
        assert result == {"file_refs": []}

    def test_path_call_with_existing_file(self, tmp_project):
        (tmp_project / "app_control.py").write_text("print('ok')\n", encoding="utf-8")
        (tmp_project / "main.py").write_text('Path("app_control.py")\n', encoding="utf-8")
        result = run_file_refs(str(tmp_project))
        assert result["file_refs"][0]["ref"] == "app_control.py"
        assert result["file_refs"][0]["type"] == "Path()"
        assert result["file_refs"][0]["exists"] is True

    def test_path_call_with_missing_file(self, tmp_project):
        (tmp_project / "main.py").write_text('Path("missing.py")\n', encoding="utf-8")
        result = run_file_refs(str(tmp_project))
        assert result["file_refs"][0]["ref"] == "missing.py"
        assert result["file_refs"][0]["exists"] is False

    def test_open_call(self, tmp_project):
        (tmp_project / "data.json").write_text('{"key": "val"}', encoding="utf-8")
        (tmp_project / "loader.py").write_text('open("data.json")\n', encoding="utf-8")
        result = run_file_refs(str(tmp_project))
        assert result["file_refs"][0]["ref"] == "data.json"
        assert result["file_refs"][0]["type"] == "open()"

    def test_subprocess_script_ref(self, tmp_project):
        (tmp_project / "script.py").write_text("print('hi')\n", encoding="utf-8")
        (tmp_project / "runner.py").write_text(
            'subprocess.Popen(["python", "script.py"])\n', encoding="utf-8"
        )
        result = run_file_refs(str(tmp_project))
        assert result["file_refs"][0]["ref"] == "script.py"
        assert result["file_refs"][0]["type"] == "subprocess"

    def test_bare_string_no_extension(self, tmp_project):
        (tmp_project / "config.py").write_text(
            'some_var = "some_string"\n', encoding="utf-8"
        )
        result = run_file_refs(str(tmp_project))
        assert result == {"file_refs": []}

    def test_skip_dir_not_scanned(self, tmp_project):
        p = tmp_project / ".venv" / "lib" / "site-packages" / "pkg.py"
        p.parent.mkdir(parents=True)
        p.write_text('Path("internal.py")\n', encoding="utf-8")
        result = run_file_refs(str(tmp_project))
        assert result == {"file_refs": []}

    def test_line_number_correct(self, tmp_project):
        (tmp_project / "app.py").write_text("x = 1\n", encoding="utf-8")
        (tmp_project / "main.py").write_text(
            "import os\n" 'Path("app.py")\n' "print('done')\n",
            encoding="utf-8",
        )
        result = run_file_refs(str(tmp_project))
        assert result["file_refs"][0]["line"] == 2

    def test_single_quote_path(self, tmp_project):
        (tmp_project / "util.py").write_text("print('ok')\n", encoding="utf-8")
        (tmp_project / "main.py").write_text("Path('util.py')\n", encoding="utf-8")
        result = run_file_refs(str(tmp_project))
        assert result["file_refs"][0]["ref"] == "util.py"

    def test_format_plain(self, tmp_project):
        (tmp_project / "app_control.py").write_text("print('ok')\n", encoding="utf-8")
        (tmp_project / "main.py").write_text('Path("app_control.py")\n', encoding="utf-8")
        result = run_file_refs(str(tmp_project))
        text = format_plain(result)
        assert "app_control.py" in text
        assert "✓" in text

    def test_format_plain_empty(self, tmp_project):
        result = run_file_refs(str(tmp_project))
        assert format_plain(result) == ""


# ===================================================================
# format_plain — 自动分发器
# ===================================================================

class TestFormatPlainDispatch:
    def test_urls_data_dispatched_correctly(self):
        data = {"hardcoded_urls": [{"file": "x.py", "ports": [8080]}]}
        text = format_plain(data)
        assert "硬编码" in text

    def test_paths_data_dispatched_correctly(self):
        data = {"local_paths": [{"file": "x.py", "paths": ["C:\\data"]}]}
        text = format_plain(data)
        assert "本地路径" in text

    def test_entries_data_dispatched_correctly(self):
        data = {"entry_points": [{"file": "x.py", "type": "main_guard", "line": 1, "context": "test"}]}
        text = format_plain(data)
        assert "入口点" in text

    def test_file_refs_data_dispatched_correctly(self):
        data = {"file_refs": [{"file": "x.py", "line": 1, "ref": "y.py", "type": "Path()", "exists": True}]}
        text = format_plain(data)
        assert "文件引用" in text

    def test_empty_data_returns_empty_string(self):
        assert format_plain({}) == ""
