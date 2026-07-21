"""
模型引用扫描模块 — 从代码中提取模型/权重文件引用、HuggingFace 模型 ID 等。

用法:
    from extractors.model_refs import run
    result = run("/path/to/project")

# ⚠️ 本文件为单一事实源。skill 副本（~/.workbuddy/skills/project-insight/scripts/extractors/model_refs.py）
#    由本文件同步生成。修改本文件后请同步 skill 副本。
"""

import json
import re
from collections import Counter
from pathlib import Path

from . import iter_project_files


# 模型文件路径引用 — 要求点前至少一个词字符（拒绝孤立扩展名），扩展名大小写不敏感
MODEL_FILE_PATTERN = re.compile(
    r"""['"]([^'"]*\w\.(?i:onnx|pt|pth|bin|safetensors|gguf|ckpt|h5|tflite|mlmodel))['"]"""
)

# HuggingFace/ModelScope 模型 ID
MODEL_ID_PATTERN = re.compile(
    r"""(?:from_pretrained|snapshot_download|AutoModel)\s*\(\s*['\"]([^'\"]+)['\"]"""
)

# 模型目录配置 — 分 quoted / unquoted 双分支
# 注意 raw string 中 `\s` 是字面反斜杠+s，所以这里用 [^\s,...]（单反斜杠）
MODEL_DIR_PATTERN = re.compile(
    r"""(?:model_dir|model_path|checkpoint|weights)\s*[=:]\s*(?:['"]([^'"]+)['"]|([^\s,)\]}"']+))"""
)

# 模型扩展名 — 被 JSON 路径与正则路径共同使用
MODEL_EXTS = ('.onnx', '.pt', '.pth', '.bin', '.safetensors',
              '.gguf', '.ckpt', '.h5', '.tflite', '.mlmodel')


def looks_like_model_path(value: str) -> bool:
    """判断一个字符串是否看起来像模型文件路径。

    与 MODEL_FILE_PATTERN 语义对齐：
    - 扩展名大小写不敏感
    - 点前至少一个词字符（拒绝孤立扩展名）
    - 仅关注扩展名匹配，不要求路径分隔符
    """
    v = value.strip().lower()
    if not v.endswith(MODEL_EXTS):
        return False
    dot = v.rfind('.')
    return dot > 0 and (v[dot - 1].isalnum() or v[dot - 1] in '_-')


def _scan_json_file(content: str) -> list:
    """用 JSON 解析遍历 string value 提取模型路径。

    替代文本正则——对结构化数据更可靠，对 weight_map 类重复天然免疫。
    解析失败时回退到正则路径。
    """
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        return None  # 解析失败信号，调用方回退到正则

    result = []

    def _walk(obj):
        if isinstance(obj, dict):
            for v in obj.values():
                _walk(v)
        elif isinstance(obj, list):
            for item in obj:
                _walk(item)
        elif isinstance(obj, str) and looks_like_model_path(obj):
            result.append(obj)

    _walk(data)
    return result


def _scan_file(filepath: str, rel: str) -> dict:
    """扫描单个文件中的模型引用"""
    try:
        content = Path(filepath).read_text(encoding='utf-8', errors='replace')
    except Exception:
        return {}

    # ⚠️ 跳过 model.safetensors.index.json — 它本身是模型元数据，不是引用模型的代码。
    # 这类 JSON 包含 weight_map（数百个 weight → shard 映射），
    # 用 regex 扫描会导致同一个 shard 文件名被匹配数百次，使输出爆炸。
    if str(filepath).endswith('.safetensors.index.json'):
        return {}

    result = {}

    if str(filepath).endswith('.json'):
        # JSON 路径：结构化解析，只遍历 string value
        raw_files = _scan_json_file(content)
        if raw_files is None:
            # JSON 解析失败 → 回退到正则路径
            raw_files = [m.group(1) for m in MODEL_FILE_PATTERN.finditer(content)]
        if raw_files:
            freq = Counter(raw_files)
            result['model_files'] = [
                {'path': p, 'count': c} for p, c in freq.most_common()
            ]
    else:
        # 正则路径：对自由文本用正则提取
        freq = Counter(m.group(1) for m in MODEL_FILE_PATTERN.finditer(content))
        if freq:
            result['model_files'] = [
                {'path': p, 'count': c} for p, c in freq.most_common()
            ]

    # 模型 ID（去重 + 频次计数）
    freq = Counter(m.group(1) for m in MODEL_ID_PATTERN.finditer(content))
    if freq:
        result['model_ids'] = [
            {'id': i, 'count': c} for i, c in freq.most_common()
        ]

    # 模型目录配置（去重 + 频次计数）
    freq = Counter(m.group(1) or m.group(2) for m in MODEL_DIR_PATTERN.finditer(content))
    if freq:
        result['model_dirs'] = [
            {'path': d, 'count': c} for d, c in freq.most_common()
        ]

    return result


def run(root_dir: str) -> dict:
    """提取项目中的模型/权重文件引用"""
    root = Path(root_dir)
    findings = []
    all_model_files = []
    all_model_ids = []
    all_model_dirs = []

    extensions = ('.bat', '.cfg', '.ini', '.json', '.md', '.ps1',
                  '.py', '.sh', '.toml', '.yaml', '.yml')
    for rel_f in iter_project_files(root, extensions=extensions):
        f = root / rel_f
        result = _scan_file(str(f), str(rel_f))
        if result:
            rel = str(rel_f)
            entry = {'file': rel}
            if 'model_files' in result:
                entry['model_files'] = result['model_files']
                all_model_files.extend(
                    item['path'] for item in result['model_files']
                )
            if 'model_ids' in result:
                entry['model_ids'] = result['model_ids']
                all_model_ids.extend(
                    item['id'] for item in result['model_ids']
                )
            if 'model_dirs' in result:
                entry['model_dirs'] = result['model_dirs']
                all_model_dirs.extend(
                    item['path'] for item in result['model_dirs']
                )
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
                parts.append(
                    "文件: " + ", ".join(
                        f"{f['path']} (x{f['count']})" if f['count'] > 1 else f['path']
                        for f in files
                    )
                )
            if ids:
                parts.append(
                    "ID: " + ", ".join(
                        f"{i['id']} (x{i['count']})" if i['count'] > 1 else i['id']
                        for i in ids
                    )
                )
            if dirs:
                parts.append(
                    "目录: " + ", ".join(
                        f"{d['path']} (x{d['count']})" if d['count'] > 1 else d['path']
                        for d in dirs
                    )
                )
            lines.append(f"  {file}")
            for p in parts:
                lines.append(f"    └─ {p}")
    return '\n'.join(lines)
