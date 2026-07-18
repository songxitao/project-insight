"""测试 project_insight.py 主入口脚本的各个函数"""

import json
import sys
from pathlib import Path

import pytest

# scripts/ 已由 conftest.py 加入 sys.path，可直接 import
from project_insight import (
    EXTRACTOR_REGISTRY,
    ALL_MODULES,
    main,
    _print_plain,
    _print_tree,
)


# ── EXTRACTOR_REGISTRY 加载 ────────────────────────────────────

def test_registry_all_modules():
    """所有 9 个模块都成功注册到 EXTRACTOR_REGISTRY"""
    expected_modules = {
        'deps', 'imports', 'paths', 'tree', 'entries',
        'env_vars', 'local_graph', 'model_refs', 'urls',
    }
    assert set(EXTRACTOR_REGISTRY.keys()) == expected_modules
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
    # 在临时项目中创建文件使 extractor 有内容可提取
    (tmp_project / "hello.py").write_text("import os\nimport sys\n", encoding="utf-8")
    monkeypatch.setattr(sys, 'argv', ['prog', str(tmp_project)])
    main()
    captured = capsys.readouterr()
    # 至少应有输出且不含错误信息
    assert captured.out.strip()
    assert '错误' not in captured.out


def test_main_json_format(tmp_project, monkeypatch, capsys):
    """--format json 应输出合法 JSON"""
    (tmp_project / "hello.py").write_text("import os\n", encoding="utf-8")
    monkeypatch.setattr(sys, 'argv', ['prog', str(tmp_project), '--format', 'json'])
    main()
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert isinstance(data, dict)


def test_main_with_modules(tmp_project, monkeypatch, capsys):
    """--modules 参数只运行指定的模块"""
    (tmp_project / "hello.py").write_text("import os\nimport sys\n", encoding="utf-8")
    monkeypatch.setattr(sys, 'argv', ['prog', str(tmp_project), '--modules', 'deps,imports', '--format', 'json'])
    main()
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert 'source_imports' in data
    # 确保其他模块未运行
    assert 'local_paths' not in data
    assert 'project_tree' not in data


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


# ── _print_plain() ─────────────────────────────────────────────

def test_print_plain(capsys):
    """_print_plain 能输出各种字段格式"""
    result = {
        'pyproject_deps': ['numpy', 'requests'],
        'requirements_deps': ['flask'],
        'source_imports': {'main.py': ['os', 'sys']},
        'install_scripts': [{'file': 'setup.sh', 'packages': ['torch']}],
        'local_paths': [{'file': 'config.py', 'paths': ['C:\\data']}],
        'project_tree': {
            'path': 'src',
            'children': [
                {'path': 'main.py', 'tag': 'py', 'size_kb': 1, 'lines': 10},
            ],
        },
        'entry_points': [
            {'type': 'function', 'file': 'main.py', 'line': 1, 'context': 'def main():'},
        ],
        'api_endpoints': [
            {'route': '/api/v1', 'file': 'app.py', 'line': 10},
        ],
        'env_vars': {
            'python_sources': ['.env'],
            'env_files': ['.env.example'],
            'docker_compose': [],
        },
        'env_vars_summary': [
            {'name': 'API_KEY', 'required': True, 'sources': ['.env']},
        ],
        'local_dep_graph': {'main.py': ['utils']},
        'model_refs': [
            {
                'file': 'model.py',
                'model_files': ['model.pt'],
                'model_ids': [],
                'model_dirs': [],
            },
        ],
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
    }
    _print_plain(result)
    captured = capsys.readouterr()

    # 验证各类字段都被正确输出
    assert 'project-insight 项目信息摘要' in captured.out
    assert 'numpy' in captured.out
    assert 'flask' in captured.out
    assert 'main.py' in captured.out
    assert 'API_KEY' in captured.out
    assert '/api/v1' in captured.out


# ── _print_tree() ──────────────────────────────────────────────

def test_print_tree(capsys):
    """_print_tree 能递归打印树结构"""
    tree = {
        'path': 'project',
        'children': [
            {
                'path': 'src',
                'children': [
                    {'path': 'main.py', 'tag': 'py', 'size_kb': 2, 'lines': 50},
                ],
            },
            {'path': 'README.md', 'tag': 'md', 'size_kb': 1, 'lines': 10},
        ],
    }
    _print_tree(tree)
    captured = capsys.readouterr()

    # 验证递归打印了各级节点
    assert 'project/' in captured.out
    assert 'src/' in captured.out
    assert 'main.py' in captured.out
    assert 'README.md' in captured.out
