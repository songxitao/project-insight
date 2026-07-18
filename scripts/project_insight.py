#!/usr/bin/env python3
"""
project-insight — 省 token 的 AI agent 项目信息提取器。

用正则从项目中精准提取关键信息，替代全量读取。
所有模块输出合并为一个结构化 JSON 摘要。

核心设计原则：
  本项目只读代码文本文件（.py / .json / .yaml / .toml / .md 等），
  非代码内容（二进制文件、模型权重、媒体文件、大体积数据）不读、不解析。
  各模块内部通过扩展名白名单 + 文件大小上限实现尺度保护。

用法:
    python scripts/project_insight.py [path] [--format json|plain] [--modules mod1,mod2,...]
"""

import argparse
import json
import sys
from pathlib import Path


# 注册所有 extractor 模块
EXTRACTOR_REGISTRY = {}

try:
    from extractors import deps
    EXTRACTOR_REGISTRY['deps'] = deps.run
except Exception as e:
    print(f"[WARN] deps 模块加载失败: {e}", file=sys.stderr)

try:
    from extractors import imports
    EXTRACTOR_REGISTRY['imports'] = imports.run
except Exception as e:
    print(f"[WARN] imports 模块加载失败: {e}", file=sys.stderr)

try:
    from extractors import paths
    EXTRACTOR_REGISTRY['paths'] = paths.run
except Exception as e:
    print(f"[WARN] paths 模块加载失败: {e}", file=sys.stderr)

try:
    from extractors import tree
    EXTRACTOR_REGISTRY['tree'] = tree.run
except Exception as e:
    print(f"[WARN] tree 模块加载失败: {e}", file=sys.stderr)

try:
    from extractors import entries
    EXTRACTOR_REGISTRY['entries'] = entries.run
except Exception as e:
    print(f"[WARN] entries 模块加载失败: {e}", file=sys.stderr)

try:
    from extractors import env_vars
    EXTRACTOR_REGISTRY['env_vars'] = env_vars.run
except Exception as e:
    print(f"[WARN] env_vars 模块加载失败: {e}", file=sys.stderr)

try:
    from extractors import local_graph
    EXTRACTOR_REGISTRY['local_graph'] = local_graph.run
except Exception as e:
    print(f"[WARN] local_graph 模块加载失败: {e}", file=sys.stderr)

try:
    from extractors import model_refs
    EXTRACTOR_REGISTRY['model_refs'] = model_refs.run
except Exception as e:
    print(f"[WARN] model_refs 模块加载失败: {e}", file=sys.stderr)

try:
    from extractors import urls
    EXTRACTOR_REGISTRY['urls'] = urls.run
except Exception as e:
    print(f"[WARN] urls 模块加载失败: {e}", file=sys.stderr)


ALL_MODULES = sorted(EXTRACTOR_REGISTRY.keys())


def main():
    parser = argparse.ArgumentParser(
        description='省 token 的 AI agent 项目信息提取器',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            '可用模块: ' + ', '.join(ALL_MODULES) + '\n'
            '所有模块用正则精准提取，不读文件全文。'
        ),
    )
    parser.add_argument(
        'path', nargs='?', default='.',
        help='项目根目录路径（默认当前目录）',
    )
    parser.add_argument(
        '--format', choices=['json', 'plain'], default='plain',
        help='输出格式：json（结构化）或 plain（可读文本，默认）',
    )
    parser.add_argument(
        '--modules', type=str, default=None,
        help=f'逗号分隔的模块名（默认全量）。可用: {",".join(ALL_MODULES)}',
    )
    args = parser.parse_args()

    root_dir = args.path
    fmt = args.format

    # 解析 --modules
    if args.modules:
        selected_modules = [m.strip() for m in args.modules.split(',') if m.strip()]
        # 验证模块名
        unknown = [m for m in selected_modules if m not in EXTRACTOR_REGISTRY]
        if unknown:
            print(f"错误: 未知模块 {unknown}，可用模块: {ALL_MODULES}", file=sys.stderr)
            sys.exit(1)
    else:
        selected_modules = ALL_MODULES

    # 确保路径存在
    if not Path(root_dir).exists():
        print(f"错误: 路径 '{root_dir}' 不存在", file=sys.stderr)
        sys.exit(1)

    # 执行选中的模块
    result = {}
    for module_name in selected_modules:
        runner = EXTRACTOR_REGISTRY.get(module_name)
        if not runner:
            continue
        try:
            module_result = runner(root_dir)
            result.update(module_result)
        except Exception as e:
            result[module_name] = {'error': str(e)}

    # 输出
    if fmt == 'json':
        print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    else:
        _print_plain(result)


def _print_plain(result: dict):
    """以可读文本格式输出"""
    print('=' * 60)
    print('project-insight 项目信息摘要')
    print('=' * 60)

    for key, value in result.items():
        if isinstance(value, dict) and 'error' in value:
            print(f"\n⚠️  {key}: 错误 — {value['error']}")
            continue

        if key == 'pyproject_deps' and value:
            print(f"\n📦 pyproject.toml 依赖 ({len(value)} 项):")
            for d in sorted(value):
                print(f"  • {d}")

        elif key == 'requirements_deps' and value:
            print(f"\n📜 requirements 依赖 ({len(value)} 项):")
            for d in sorted(value):
                print(f"  • {d}")

        elif key == 'source_imports' and value:
            print(f"\n🔗 源码 import ({len(value)} 个文件):")
            for f, imps in sorted(value.items()):
                print(f"  {f} → {', '.join(sorted(imps))}")

        elif key == 'install_scripts' and value:
            print(f"\n📜 安装脚本中的依赖:")
            for s in value:
                print(f"  {s['file']}: {', '.join(s.get('packages', []))}")

        elif key == 'local_paths' and value:
            print(f"\n⚠️  本地路径硬编码:")
            for s in value:
                for p in s['paths']:
                    print(f"  {s['file']} → {p}")

        elif key == 'project_tree' and value:
            print(f"\n🌳 项目骨架树:")
            _print_tree(value, indent=2)

        elif key == 'entry_points' and value:
            print(f"\n🚪 入口点 ({len(value)} 个):")
            for ep in value:
                print(f"  [{ep['type']}] {ep['file']}:{ep['line']}")
                print(f"    └─ {ep['context'][:80]}...")

        elif key == 'api_endpoints' and value:
            print(f"\n🌐 API 端点 ({len(value)} 个):")
            for ep in value:
                print(f"  {ep['route']}  ({ep['file']}:{ep['line']})")

        elif key == 'env_vars' and isinstance(value, dict):
            print(f"\n🔑 环境变量:")
            py_count = len(value.get('python_sources', []))
            env_count = len(value.get('env_files', []))
            dc_count = len(value.get('docker_compose', []))
            print(f"  Python 来源: {py_count} 个文件")
            print(f"  环境文件: {env_count} 个文件")
            print(f"  Docker Compose: {dc_count} 个文件")

        elif key == 'env_vars_summary' and value:
            for v in value:
                req = '必需' if v['required'] else '可选'
                srcs = ', '.join(set(v['sources']))
                print(f"  {req} {v['name']}  (来自: {srcs})")

        elif key == 'local_dep_graph' and value:
            print(f"\n🔀 本地模块依赖图 ({len(value)} 条):")
            for f, refs in sorted(value.items()):
                print(f"  {f} → {', '.join(refs)}")

        elif key == 'model_refs' and value:
            print(f"\n🤖 模型引用 ({len(value)} 个文件):")
            for entry in value:
                file = entry['file']
                files = entry.get('model_files', [])
                ids = entry.get('model_ids', [])
                dirs = entry.get('model_dirs', [])
                parts = []
                if files: parts.append(f"文件: {', '.join(files)}")
                if ids: parts.append(f"ID: {', '.join(ids)}")
                if dirs: parts.append(f"目录: {', '.join(dirs)}")
                print(f"  {file}")
                for p in parts:
                    print(f"    └─ {p}")

        elif key == 'hardcoded_urls' and value:
            print(f"\n🔗 硬编码 URL/端口/IP ({len(value)} 个文件):")
            for entry in value:
                file = entry['file']
                parts = []
                if 'ports' in entry: parts.append(f"端口: {entry['ports']}")
                if 'localhost_ports' in entry: parts.append(f"localhost:{entry['localhost_ports']}")
                if 'zero_host_ports' in entry: parts.append(f"0.0.0.0:{entry['zero_host_ports']}")
                if 'urls' in entry: parts.append(f"URL: {entry['urls']}")
                if 'ips' in entry: parts.append(f"IP: {entry['ips']}")
                print(f"  {file}")
                for p in parts:
                    print(f"    └─ {p}")

        elif key.endswith('_summary') and isinstance(value, dict):
            # 跳过汇总字段，已经在对应的主字段中显示了
            pass

        elif isinstance(value, list) and not value:
            pass

        elif isinstance(value, dict) and not value:
            pass


def _print_tree(node, indent: int = 0):
    """递归打印树节点"""
    if node is None:
        return

    prefix = '  ' * indent

    if 'children' in node:
        # 目录节点
        print(f"{prefix}📁 {node['path']}/")
        for child in node.get('children', []):
            _print_tree(child, indent + 1)
    else:
        # 文件节点
        tag = node.get('tag', '')
        size = node.get('size_kb', 0)
        lines = node.get('lines', 0)
        tag_str = f" {tag}" if tag else ""
        print(f"{prefix}📄 {node['path']}{tag_str}  ({size} KB, {lines} 行)")


if __name__ == '__main__':
    main()
