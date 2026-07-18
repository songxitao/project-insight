"""测试 tree.py: 项目骨架树提取。"""
from pathlib import Path

from extractors.tree import run


def make_file(base: Path, rel_path: str, content: str = ""):
    target = base / rel_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return target


class TestEmptyDirectory:
    def test_empty_directory_returns_none(self, tmp_project):
        result = run(str(tmp_project))
        assert result["project_tree"] is None


class TestFileAndDirectoryNodes:
    def test_file_node_has_path_size_lines(self, tmp_project):
        make_file(tmp_project, "hello.py", "line1\nline2\nline3\n")
        result = run(str(tmp_project))
        tree = result["project_tree"]
        assert tree is not None
        assert tree["type"] == "dir"
        assert tree["path"] == "."
        assert len(tree["children"]) == 1
        node = tree["children"][0]
        assert node["path"] == "hello.py"
        assert isinstance(node.get("size_kb"), (int, float))
        assert node["lines"] == 3

    def test_directory_node_has_type_and_children(self, tmp_project):
        make_file(tmp_project, "sub/deep.txt", "content")
        result = run(str(tmp_project))
        tree = result["project_tree"]
        assert tree is not None
        dir_node = tree["children"][0]
        assert dir_node["type"] == "dir"
        assert dir_node["path"] == "sub"
        assert "children" in dir_node
        assert len(dir_node["children"]) == 1
        assert dir_node["children"][0]["path"] == "sub/deep.txt"


class TestTags:
    def test_special_files_get_tags(self, tmp_project):
        make_file(tmp_project, "README.md", "# Readme\n")
        make_file(tmp_project, "pyproject.toml", "[tool]\n")
        make_file(tmp_project, "main.py", "def main(): pass\n")
        result = run(str(tmp_project))
        tree = result["project_tree"]
        assert tree is not None
        tags = {c["path"]: c.get("tag") for c in tree["children"]}
        assert tags["README.md"] == "[文档]"
        assert tags["pyproject.toml"] == "[配置]"
        assert tags["main.py"] == "[入口]"  # noqa: RUF001


class TestSkipDirs:
    def test_skip_dirs_excluded(self, tmp_project):
        make_file(tmp_project, "node_modules/pkg.py", "x=1")
        make_file(tmp_project, "__pycache__/cache.py", "y=2")
        make_file(tmp_project, "normal.py", "z=3")
        result = run(str(tmp_project))
        tree = result["project_tree"]
        assert tree is not None
        assert len(tree["children"]) == 1
        assert tree["children"][0]["path"] == "normal.py"
