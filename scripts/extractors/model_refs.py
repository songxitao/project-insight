"""
模型引用扫描模块 — 从代码中提取模型/权重文件引用、HuggingFace 模型 ID 等。

用法:
    from extractors.model_refs import run
    result = run("/path/to/project")
"""

import re
from pathlib import Path


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


def _is_skip_dirs(p: Path) -> bool:
    skip = {'__pycache__', '.git', 'venv', '.venv', 'env',
            'node_modules', 'build', 'dist', '.pytest_cache',
            '.ruff_cache', '.workbuddy', 'output', 'testset',
            '.pilot_venv', '.superpowers', '.agents', '.claude',
            '.scratch'}
    return any(part.name in skip for part in p.parents)


def run(root_dir: str) -> dict:
    """提取项目中的模型/权重文件引用"""
    root = Path(root_dir)
    findings = []
    all_model_files = []
    all_model_ids = []
    all_model_dirs = []

    for f in sorted(root.rglob('*')):
        if not f.is_file():
            continue
        if _is_skip_dirs(f):
            continue

        ext = f.suffix.lower()
        if ext not in ('.py', '.bat', '.sh', '.ps1', '.yaml', '.yml', '.json'):
            continue

        result = _scan_file(str(f), str(f.relative_to(root)))
        if result:
            rel = str(f.relative_to(root))
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
