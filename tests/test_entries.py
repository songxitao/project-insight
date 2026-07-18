"""测试 entries.py: 入口点与 API 端点提取。"""
from pathlib import Path

from extractors.entries import run


def make_file(base: Path, rel_path: str, content: str = ""):
    target = base / rel_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return target


class TestEntryPoints:
    def test_main_guard_detected(self, tmp_project):
        make_file(
            tmp_project, "main.py", "if __name__ == '__main__':\n    main()\n"
        )
        result = run(str(tmp_project))
        assert len(result["entry_points"]) == 1
        ep = result["entry_points"][0]
        assert ep["type"] == "main_guard"
        assert ep["file"] == "main.py"

    def test_web_framework_detected(self, tmp_project):
        make_file(tmp_project, "app.py", "from fastapi import FastAPI\napp = FastAPI()\n")
        result = run(str(tmp_project))
        types = [ep["type"] for ep in result["entry_points"]]
        assert "web_framework" in types

    def test_no_entry_points_returns_empty(self, tmp_project):
        make_file(tmp_project, "utils.py", "def helper(x):\n    return x\n")
        result = run(str(tmp_project))
        assert result["entry_points"] == []


class TestApiEndpoints:
    def test_api_route_extracted(self, tmp_project):
        make_file(
            tmp_project, "api.py", "@app.get('/hello')\nasync def hello(): pass\n"
        )
        result = run(str(tmp_project))
        assert len(result["api_endpoints"]) == 1
        route = result["api_endpoints"][0]
        assert route["route"] == "/hello"
        assert route["file"] == "api.py"


class TestLongFile:
    def test_long_file_snippet_only_scans_head_and_tail(self, tmp_project):
        lines = ["x = 1\n"] * 240
        lines[9] = "if __name__ == '__main__':\n"       # head → 应检测
        lines[209] = "if __name__ == '__main__':\n"     # 中间 → 不应检测
        content = "".join(lines)
        make_file(tmp_project, "long.py", content)
        result = run(str(tmp_project))
        assert len(result["entry_points"]) == 1
        # head 中那条的 line 编号
        assert result["entry_points"][0]["line"] == 10


class TestPatternLines:
    def test_pattern_definition_lines_not_matched(self, tmp_project):
        make_file(tmp_project, "fake_patterns.py", """\
import re
ENTRY_PATTERNS = [
    (re.compile(r"if\\s+__name__\\s*==\\s*['\\"]__main__['\\"]"), 'main_guard'),
]
x = 42
""")
        result = run(str(tmp_project))
        assert len(result["entry_points"]) == 0
