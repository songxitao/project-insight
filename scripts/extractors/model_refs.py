"""
模型引用扫描模块 — 从代码中提取模型/权重文件引用、HuggingFace 模型 ID 等。

用法:
    from extractors.model_refs import run
    result = run("/path/to/project")
"""

import re
from pathlib import Path

from . import iter_project_files


# 模型文件路径引用
MODEL_FILE_PATTERN = re.compile(
    r"""['\"]([^'\"]*\.(?:onnx|pt|pth|bin|safetensors|gguf|ckpt|h5|tflite|mlmodel))['\"]"""
)

# HuggingFace/ModelScope 模型 ID
MODEL_ID_PATTERN = re.compile(
    r"""(?:from_pretrained|snapshot_download|AutoModel)\s*\(\s*['\"]([^'\"]+)['\"]"""
)

# 模型目录配置
MODEL_DIR_PATTERN = re.compile(
    r"""(?:model_dir|model_path|checkpoint|weights)\s*[=:]\s*['\"]?([^'\"\\s,\)]+)"""
)


def _scan_file(filepath: str, rel: str) -> dict:
    """扫描单个文件中的模型引用"""
    try:
        content = Path(filepath).read_text(encoding='utf-8', errors='replace')
    except Exception:
        return {}

    result = {}
    # 模型文件路径
    model_files = [m.group(1) for m in MODEL_FILE_PATTERN.finditer(content)]
    if model_files:
        result['model_files'] = model_files

    # 模型 ID
    model_ids = [m.group(1) for m in MODEL_ID_PATTERN.finditer(content)]
    if model_ids:
        result['model_ids'] = model_ids

    # 模型目录配置
    model_dirs = [m.group(1) for m in MODEL_DIR_PATTERN.finditer(content)]
    if model_dirs:
        result['model_dirs'] = model_dirs

    return result


def run(root_dir: str) -> dict:
    """提取项目中的模型/权重文件引用"""
    root = Path(root_dir)
    findings = []
    all_model_files = []
    all_model_ids = []
    all_model_dirs = []

    extensions = ('.py', '.bat', '.sh', '.ps1', '.yaml', '.yml', '.json')
    for rel_f in iter_project_files(root, extensions=extensions):
        f = root / rel_f
        result = _scan_file(str(f), str(rel_f))
        if result:
            rel = str(rel_f)
            entry = {'file': rel}
            if 'model_files' in result:
                entry['model_files'] = result['model_files']
                all_model_files.extend(result['model_files'])
            if 'model_ids' in result:
                entry['model_ids'] = result['model_ids']
                all_model_ids.extend(result['model_ids'])
            if 'model_dirs' in result:
                entry['model_dirs'] = result['model_dirs']
                all_model_dirs.extend(result['model_dirs'])
            findings.append(entry)

    return {
        'model_refs': findings,
        'model_refs_summary': {
            'unique_model_files': sorted(set(all_model_files)),
            'unique_model_ids': sorted(set(all_model_ids)),
            'unique_model_dirs': sorted(set(all_model_dirs)),
        },
    }


def format_plain(data: dict) -> str:
    """T3 统一 plain 文本输出"""
    lines = []
    entries = data.get('model_refs', [])
    if entries:
        lines.append(f"\n🤖 模型引用 ({len(entries)} 个文件):")
        for entry in entries:
            file = entry.get('file', '')
            files = entry.get('model_files', [])
            ids = entry.get('model_ids', [])
            dirs = entry.get('model_dirs', [])
            parts = []
            if files:
                parts.append(f"文件: {', '.join(files)}")
            if ids:
                parts.append(f"ID: {', '.join(ids)}")
            if dirs:
                parts.append(f"目录: {', '.join(dirs)}")
            lines.append(f"  {file}")
            for p in parts:
                lines.append(f"    └─ {p}")
    return '\n'.join(lines)
