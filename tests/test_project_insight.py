"""测试 project_insight.py 主入口脚本的各个函数"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

# scripts/ 已由 conftest.py 加入 sys.path，可直接 import
from project_insight import (
    REGISTRY,
    ALL_MODULES,
    main,
    _print_plain,
)


# ── REGISTRY 加载 ────────────────────────────────────

def test_registry_all_modules():
    """所有 10 个模块都成功注册到 REGISTRY"""
    expected_modules = {
        'deps', 'file_refs', 'imports', 'paths', 'tree', 'entries',
        'env_vars', 'local_graph', 'model_refs', 'urls',
    }
    assert set(REGISTRY.keys()) == expected_modules
    # 验证新结构
    for name in expected_modules:
        entry = REGISTRY[name]
        assert 'run' in entry
        assert 'mod' in entry
        assert callable(entry['run'])
    assert ALL_MODULES == sorted(expected_modules)


# ── main() 各种调用方式 ────────────────────────────────────────

def test_main_default_path(monkeypatch, capsys):
    """不带参数应使用当前目录并产生输出"""
    monkeypatch.setattr(sys, 'argv', ['prog'])
    main()
    captured = capsys.readouterr()
    assert 'project-insight 项目信息摘要' in captured.out


def test_main_with_path(tmp_project, monkeypatch, capsys):
    """指定临时目录应成功执行并产生输出"""
    (tmp_project / "hello.py").write_text("import os\nimport sys\n", encoding="utf-8")
    monkeypatch.setattr(sys, 'argv', ['prog', str(tmp_project)])
    main()
    captured = capsys.readouterr()
    assert captured.out.strip()
    assert '错误' not in captured.out


def test_main_json_format(tmp_project, monkeypatch, capsys):
    """--format json 应输出合法 JSON（命名空间结构）"""
    (tmp_project / "hello.py").write_text("import os\n", encoding="utf-8")
    monkeypatch.setattr(sys, 'argv', ['prog', str(tmp_project), '--format', 'json'])
    main()
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert isinstance(data, dict)
    module_keys = {'deps', 'entries', 'env_vars', 'imports', 'local_graph',
                   'model_refs', 'paths', 'tree', 'urls'}
    assert module_keys.issubset(set(data.keys()))


def test_main_with_modules(tmp_project, monkeypatch, capsys):
    """--modules 参数只运行指定的模块"""
    (tmp_project / "hello.py").write_text("import os\nimport sys\n", encoding="utf-8")
    monkeypatch.setattr(sys, 'argv', ['prog', str(tmp_project), '--modules', 'deps,imports', '--format', 'json'])
    main()
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert 'imports' in data
    assert 'deps' in data
    assert 'tree' not in data
    assert 'paths' not in data


def test_main_invalid_path(monkeypatch):
    """无效路径应 exit(1)"""
    monkeypatch.setattr(sys, 'argv', ['prog', '/nonexistent_path_xyz_123'])
    with pytest.raises(SystemExit) as exc_info:
        main()
    assert exc_info.value.code == 1


def test_main_unknown_module(tmp_project, monkeypatch):
    """未知模块名应 exit(1)"""
    monkeypatch.setattr(sys, 'argv', ['prog', str(tmp_project), '--modules', 'unknown_mod'])
    with pytest.raises(SystemExit) as exc_info:
        main()
    assert exc_info.value.code == 1


# ── --strict 标志 ────────────────────────────────────────────

def test_main_default_with_broken_refs(tmp_project, monkeypatch, capsys):
    """默认模式 + 有断裂引用 → exit 0, stderr 有 warn"""
    (tmp_project / "test.py").write_text(
        'ref = Path("missing.py")\n', encoding="utf-8"
    )
    monkeypatch.setattr(sys, 'argv', ['prog', str(tmp_project)])
    main()
    captured = capsys.readouterr()
    assert '[WARN]' in captured.err


def test_main_strict_with_broken_refs(tmp_project, monkeypatch):
    """--strict + 有断裂引用 → exit 1"""
    (tmp_project / "test.py").write_text(
        'ref = Path("missing.py")\n', encoding="utf-8"
    )
    monkeypatch.setattr(sys, 'argv', ['prog', str(tmp_project), '--strict'])
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 1


def test_main_strict_without_broken_refs(tmp_project, monkeypatch, capsys):
    """--strict + 无断裂引用 → exit 0"""
    (tmp_project / "test.py").write_text(
        "import os\n", encoding="utf-8"
    )
    monkeypatch.setattr(sys, 'argv', ['prog', str(tmp_project), '--strict'])
    main()
    captured = capsys.readouterr()
    assert captured.out.strip()


# ── _print_plain() — 通用分发器 ────────────────────────────────

def test_print_plain(capsys):
    """_print_plain 能通过通用分发和 format_plain 输出各种字段"""
    result = {
        'deps': {
            'pyproject_deps': ['numpy', 'requests'],
            'requirements_deps': ['flask'],
            'install_scripts': [{'file': 'setup.sh', 'packages': ['torch']}],
        },
        'entries': {
            'entry_points': [
                {'type': 'function', 'file': 'main.py', 'line': 1, 'context': 'def main():'},
            ],
            'api_endpoints': [
                {'route': '/api/v1', 'file': 'app.py', 'line': 10},
            ],
        },
        'env_vars': {
            'env_vars': {
                'python_sources': ['.env'],
                'env_files': ['.env.example'],
                'docker_compose': [],
            },
            'env_vars_summary': [
                {'name': 'API_KEY', 'required': True, 'sources': ['.env']},
            ],
        },
        'imports': {
            'source_imports': {'main.py': ['os', 'sys']},
        },
        'paths': {
            'local_paths': [{'file': 'config.py', 'paths': ['C:\\data']}],
        },
        'tree': {
            'project_tree': {
                'path': 'src',
                'children': [
                    {'path': 'main.py', 'tag': 'py', 'size_kb': 1, 'lines': 10},
                ],
            },
        },
        'local_graph': {
            'local_dep_graph': {'main.py': ['utils']},
        },
        'model_refs': {
            'model_refs': [
                {
                    'file': 'model.py',
                    'model_files': [{'path': 'model.pt', 'count': 1}],
                    'model_ids': [],
                    'model_dirs': [],
                },
            ],
        },
        'urls': {
            'hardcoded_urls': [
                {
                    'file': 'config.py',
                    'urls': ['http://example.com'],
                    'ports': [],
                    'localhost_ports': [],
                    'zero_host_ports': [],
                    'ips': [],
                },
            ],
        },
    }
    _print_plain(result)
    captured = capsys.readouterr()

    assert 'project-insight 项目信息摘要' in captured.out
    assert 'numpy' in captured.out
    assert 'flask' in captured.out
    assert 'main.py' in captured.out
    assert 'API_KEY' in captured.out
    assert '/api/v1' in captured.out


# ── 端到端快照测试（subprocess） ─────────────────────────────────


def test_end_to_end_json_output():
    """对 project-insight 自身运行 --format json，验证所有模块输出"""
    project_root = Path(__file__).resolve().parent.parent
    script = project_root / "scripts" / "project_insight.py"
    result = subprocess.run(
        [sys.executable, str(script), str(project_root), "--format", "json"],
        capture_output=True, text=True, cwd=str(project_root),
    )
    assert result.returncode == 0, f"stderr: {result.stderr}"
    data = json.loads(result.stdout)

    # 断言全部 10 个模块的 key
    expected_modules = {
        'deps', 'entries', 'env_vars', 'imports', 'local_graph',
        'model_refs', 'paths', 'tree', 'urls', 'file_refs',
    }
    assert expected_modules.issubset(data.keys()), \
        f"缺少模块: {expected_modules - data.keys()}"

    # file_refs 结构断言
    assert 'file_refs' in data
    assert isinstance(data['file_refs'], dict)
    assert 'file_refs' in data['file_refs']
    assert isinstance(data['file_refs']['file_refs'], list)

    # local_graph 结构断言
    assert 'local_graph' in data
    assert isinstance(data['local_graph'], dict)
    assert 'local_dep_graph' in data['local_graph']
    assert 'broken_imports' in data['local_graph']


def test_end_to_end_plain_output():
    """--format plain 对所有模块无异常输出"""
    project_root = Path(__file__).resolve().parent.parent
    script = project_root / "scripts" / "project_insight.py"
    result = subprocess.run(
        [sys.executable, str(script), str(project_root), "--format", "plain"],
        capture_output=True, text=True, cwd=str(project_root),
    )
    assert result.returncode == 0, f"stderr: {result.stderr}"
    assert result.stdout.strip(), "plain 输出不应为空"
