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


def main() -> None:
    """CLI 入口：解析参数、执行模块、输出结果"""
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
    parser.add_argument(
        '--strict', '-s', action='store_true',
        help='严格模式：检测到断裂引用时以非零退出码退出',
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

    # 严格模式 / 断裂引用警告
    _check_broken_refs(result, args.strict)


def _check_broken_refs(result: dict, strict: bool) -> None:
    """扫描结果中的断裂引用，按模式决定行为。

    - strict=True: 打印详情到 stderr 并 sys.exit(1)
    - strict=False: 打印 [WARN] 到 stderr，不改变退出码
    """
    issues = []

    if 'file_refs' in result:
        for ref in result['file_refs'].get('file_refs', []):
            if not ref.get('exists', True):
                issues.append(f"  {ref['file']}:{ref['line']} → {ref['ref']} ({ref['type']})")

    if 'local_graph' in result:
        for fpath, imports in result['local_graph'].get('broken_imports', {}).items():
            if imports:
                for imp in imports:
                    issues.append(f"  {fpath} → broken import: {imp}")

    if issues:
        if strict:
            print("检测到断裂引用，退出码 1", file=sys.stderr)
            for msg in issues:
                print(msg, file=sys.stderr)
            sys.exit(1)
        else:
            print("[WARN] 检测到断裂引用:", file=sys.stderr)
            for msg in issues:
                print(msg, file=sys.stderr)


def _print_plain(result: dict) -> None:
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


if __name__ == '__main__':
    main()
