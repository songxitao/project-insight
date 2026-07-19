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

from extractors import REGISTRY


ALL_MODULES = sorted(REGISTRY.keys())


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
        unknown = [m for m in selected_modules if m not in REGISTRY]
        if unknown:
            print(f"错误: 未知模块 {unknown}，可用模块: {ALL_MODULES}", file=sys.stderr)
            sys.exit(1)
    else:
        selected_modules = ALL_MODULES

    # 确保路径存在
    if not Path(root_dir).exists():
        print(f"错误: 路径 '{root_dir}' 不存在", file=sys.stderr)
        sys.exit(1)

    # 执行选中的模块 — 命名空间隔离
    result = {}
    for module_name in selected_modules:
        entry = REGISTRY.get(module_name)
        if not entry:
            continue
        try:
            result[module_name] = entry['run'](root_dir)
        except Exception as e:
            result[module_name] = {'error': str(e)}

    # 输出
    if fmt == 'json':
        print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    else:
        _print_plain(result)


def _print_plain(result: dict):
    """通用分发器 — 按模块的 format_plain() 或通用兜底输出"""
    print('=' * 60)
    print('project-insight 项目信息摘要')
    print('=' * 60)

    for module_name in sorted(result.keys()):
        data = result[module_name]

        if not isinstance(data, dict):
            continue

        if 'error' in data:
            print(f"\n⚠️  {module_name}: 错误 — {data['error']}")
            continue

        if not data:
            continue

        entry = REGISTRY.get(module_name)
        if entry and hasattr(entry['mod'], 'format_plain'):
            print(entry['mod'].format_plain(data))
        else:
            print(_format_generic(module_name, data))


def _format_generic(module_name: str, data: dict) -> str:
    """通用格式化 — 按 data 内的 key 分发，返回格式化字符串"""
    lines = []
    for key, value in data.items():
        # 跳过 _summary 类 key（在主 key 中已显示）
        if key.endswith('_summary') and isinstance(value, (dict, list)):
            continue

        # 跳过空数据
        if isinstance(value, (list, dict)) and not value:
            continue

        if key == 'pyproject_deps':
            lines.append(f"\n📦 pyproject.toml 依赖 ({len(value)} 项):")
            for d in sorted(value):
                lines.append(f"  • {d}")

        elif key == 'requirements_deps':
            lines.append(f"\n📜 requirements 依赖 ({len(value)} 项):")
            for d in sorted(value):
                lines.append(f"  • {d}")

        elif key == 'source_imports':
            lines.append(f"\n🔗 源码 import ({len(value)} 个文件):")
            for f, imps in sorted(value.items()):
                lines.append(f"  {f} → {', '.join(sorted(imps))}")

        elif key == 'install_scripts':
            lines.append(f"\n📜 安装脚本中的依赖:")
            for s in value:
                lines.append(f"  {s['file']}: {', '.join(s.get('packages', []))}")

        elif key == 'local_paths':
            lines.append(f"\n⚠️  本地路径硬编码:")
            for s in value:
                for p in s['paths']:
                    lines.append(f"  {s['file']} → {p}")

        elif key == 'entry_points':
            lines.append(f"\n🚪 入口点 ({len(value)} 个):")
            for ep in value:
                lines.append(f"  [{ep['type']}] {ep['file']}:{ep['line']}")
                lines.append(f"    └─ {ep['context'][:80]}...")

        elif key == 'api_endpoints':
            lines.append(f"\n🌐 API 端点 ({len(value)} 个):")
            for ep in value:
                lines.append(f"  {ep['route']}  ({ep['file']}:{ep['line']})")

        elif key == 'local_dep_graph':
            lines.append(f"\n🔀 本地模块依赖图 ({len(value)} 条):")
            for f, refs in sorted(value.items()):
                lines.append(f"  {f} → {', '.join(refs)}")

        elif key == 'project_tree':
            lines.append(f"\n🌳 项目骨架树:")
            _append_tree(value, lines, indent=2)

    return '\n'.join(lines)


def _append_tree(node, lines: list, indent: int = 0):
    """递归追加树节点到 lines 列表"""
    if node is None:
        return

    prefix = '  ' * indent

    if 'children' in node:
        lines.append(f"{prefix}📁 {node['path']}/")
        for child in node.get('children', []):
            _append_tree(child, lines, indent + 1)
    else:
        tag = node.get('tag', '')
        size = node.get('size_kb', 0)
        lines_count = node.get('lines', 0)
        tag_str = f" {tag}" if tag else ""
        lines.append(f"{prefix}📄 {node['path']}{tag_str}  ({size} KB, {lines_count} 行)")


if __name__ == '__main__':
    main()
