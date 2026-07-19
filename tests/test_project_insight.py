"""测试 project_insight.py 主入口脚本的各个函数"""

import json
import sys
from pathlib import Path

import pytest

# scripts/ 已由 conftest.py 加入 sys.path，可直接 import
from project_insight import (
    REGISTRY,
    ALL_MODULES,
    main,
    _print_plain,
    _format_generic,
)


# ── REGISTRY 加载 ────────────────────────────────────

def test_registry_all_modules():
    """所有 9 个模块都成功注册到 REGISTRY"""
    expected_modules = {
        'deps', 'imports', 'paths', 'tree', 'entries',
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
                    'model_files': ['model.pt'],
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


# ── _format_generic() — 返回字符串 ──────────────────────────────

def test_format_generic_returns_string():
    """_format_generic 返回字符串而非直接打印"""
    data = {
        'pyproject_deps': ['numpy', 'requests'],
        'source_imports': {'main.py': ['os', 'sys']},
    }
    output = _format_generic('deps', data)
    assert isinstance(output, str)
    assert 'numpy' in output
    assert 'main.py' in output


def test_format_generic_project_tree():
    """_format_generic 能格式化 project_tree"""
    data = {
        'project_tree': {
            'path': 'project',
            'children': [
                {'path': 'main.py', 'tag': 'py', 'size_kb': 2, 'lines': 50},
            ],
        },
    }
    output = _format_generic('tree', data)
    assert isinstance(output, str)
    assert 'project/' in output
    assert 'main.py' in output


def test_format_generic_empty():
    """_format_generic 空数据返回空字符串"""
    assert _format_generic('deps', {}) == ''
    assert _format_generic('nonexistent', {}) == ''
