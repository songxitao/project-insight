"""
测试环境变量提取模块 (extractors.env_vars)
"""
import pytest
from extractors.env_vars import run, _extract_from_python, _extract_from_env, _extract_from_docker_compose
from conftest import make_file


class TestEnvVarsRun:
    def test_empty_project(self, tmp_project):
        result = run(str(tmp_project))
        assert result["env_vars"]["python_sources"] == []
        assert result["env_vars"]["env_files"] == []
        assert result["env_vars"]["docker_compose"] == []
        assert result["env_vars_summary"] == []

    def test_python_os_environ_get(self, tmp_project):
        make_file(tmp_project, "app.py", "import os\nAPI_KEY = os.environ.get('API_KEY')\n")
        result = run(str(tmp_project))
        py_src = result["env_vars"]["python_sources"]
        assert len(py_src) == 1
        assert py_src[0]["file"] == "app.py"
        assert {"name": "API_KEY", "required": False} in py_src[0]["variables"]

    def test_python_os_environ_get_with_default(self, tmp_project):
        make_file(tmp_project, "app.py", "import os\nPORT = os.environ.get('PORT', '8080')\n")
        result = run(str(tmp_project))
        py_src = result["env_vars"]["python_sources"]
        assert len(py_src) == 1
        assert {"name": "PORT", "required": False, "default": "8080"} in py_src[0]["variables"]

    def test_python_os_getenv(self, tmp_project):
        make_file(tmp_project, "app.py", "import os\nDB_URL = os.getenv('DB_URL')\n")
        result = run(str(tmp_project))
        py_src = result["env_vars"]["python_sources"]
        assert len(py_src) == 1
        assert {"name": "DB_URL", "required": False} in py_src[0]["variables"]

    def test_env_file(self, tmp_project):
        make_file(tmp_project, ".env", "SECRET_KEY=abc123\nDEBUG=true\n")
        result = run(str(tmp_project))
        env_files = result["env_vars"]["env_files"]
        assert len(env_files) == 1
        assert "SECRET_KEY" in env_files[0]["keys"]
        assert "DEBUG" in env_files[0]["keys"]

    def test_docker_compose_environment(self, tmp_project):
        make_file(tmp_project, "docker-compose.yml", (
            "version: '3'\nservices:\n  web:\n    environment:\n"
            "      REDIS_HOST=localhost\n      REDIS_PORT=6379\n"
        ))
        result = run(str(tmp_project))
        dc = result["env_vars"]["docker_compose"]
        assert len(dc) == 1
        names = [v["name"] for v in dc[0]["variables"]]
        assert "REDIS_HOST" in names
        assert "REDIS_PORT" in names

    def test_skip_dirs_ignored(self, tmp_project):
        skip_dir = tmp_project / "__pycache__"
        skip_dir.mkdir(parents=True)
        make_file(skip_dir, "secret.py", "KEY=os.environ.get('SECRET')\n")
        result = run(str(tmp_project))
        assert result["env_vars"]["python_sources"] == []

    def test_summary_aggregation(self, tmp_project):
        make_file(tmp_project, "a.py", "import os\nX=os.environ.get('X')\n")
        make_file(tmp_project, "b.py", "import os\nX=os.environ.get('X')\n")
        result = run(str(tmp_project))
        summary = result["env_vars_summary"]
        x_vars = [s for s in summary if s["name"] == "X"]
        assert len(x_vars) == 1
        assert len(x_vars[0]["sources"]) == 2


class TestExtractHelpers:
    def test_extract_from_python_empty(self, tmp_project):
        f = make_file(tmp_project, "x.py", "a = 1\nb = 2\n")
        assert _extract_from_python(str(f)) == []

    def test_extract_from_env_empty(self, tmp_project):
        f = make_file(tmp_project, ".env", "# comment\n")
        assert _extract_from_env(str(f)) == []

    def test_extract_from_docker_empty(self, tmp_project):
        f = make_file(tmp_project, "dc.yml", "version: '3'\n")
        assert _extract_from_docker_compose(str(f)) == []

    def test_docker_key_only(self, tmp_project):
        f = make_file(tmp_project, "dc.yml", (
            "services:\n  web:\n    environment:\n      FOO\n      BAR\n"
        ))
        result = _extract_from_docker_compose(str(f))
        names = [r["name"] for r in result]
        assert "FOO" in names
        assert "BAR" in names

    def test_docker_kv_format(self, tmp_project):
        f = make_file(tmp_project, "dc.yml", (
            "services:\n  web:\n    environment:\n      FOO=hello\n      BAR=world\n"
        ))
        result = _extract_from_docker_compose(str(f))
        foos = [r for r in result if r["name"] == "FOO"]
        assert len(foos) == 1
        assert foos[0]["value"] == "hello"
