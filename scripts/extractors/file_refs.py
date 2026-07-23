"""
文件引用扫描模块 — 检测代码中的文件引用（Path() / open() / subprocess 脚本引用）。

用法:
    from extractors.file_refs import run
    result = run("/path/to/project")
"""

import re
from pathlib import Path

from . import iter_project_files, safe_read


# 扩展名白名单
ALLOWED_EXTS = frozenset({
    '.py', '.json', '.yaml', '.yml', '.csv', '.txt',
    '.md', '.toml', '.cfg', '.ini', '.conf', '.xml',
})

# 脚本扩展名（subprocess 专用）
SCRIPT_EXTS = frozenset({'.py', '.sh', '.bat', '.ps1'})

# Path("xxx.py") / Path('xxx.json')  / open("xxx.csv") / open('xxx.txt')
# 也匹配 pathlib.Path("file.py") 带模块前缀
QUOTED_REF_PATTERN = re.compile(
    r"""(?P<type>(?:pathlib\.)?Path|open)\s*\(\s*["'](?P<path>[^"']+)["']\s*\)"""
)

# subprocess.Popen(["python", "script.py"]) / subprocess.run("script.py")
SCRIPT_REF_PATTERN = re.compile(
    r"""(?:subprocess\.\w+|subprocess)\s*\([^)]*?["']([^"']+\.(?:
        py|sh|bat|ps1))["']""",
    re.VERBOSE,
)


def _has_allowed_ext(path_str: str) -> bool:
    """检查文件路径是否有允许的扩展名"""
    return Path(path_str).suffix.lower() in ALLOWED_EXTS


def run(root_dir: str) -> dict:
    """提取项目中的文件引用"""
    root = Path(root_dir)
    findings = []

    # 一期只扫 .py 文件
    for rel_f in iter_project_files(root, extensions=('.py',)):
        f = root / rel_f
        content = safe_read(str(f))
        if not content:
            continue

        rel = str(rel_f)
        seen_keys = set()  # 去重: (line, ref)

        # --- Path() / open() ---
        for m in QUOTED_REF_PATTERN.finditer(content):
            ref_type = m.group('type')
            ref_path = m.group('path')
            if not _has_allowed_ext(ref_path):
                continue

            line_num = content[:m.start()].count('\n') + 1
            exists = (root / ref_path).exists()

            key = (line_num, ref_path)
            if key not in seen_keys:
                seen_keys.add(key)
                findings.append({
                    'file': rel,
                    'line': line_num,
                    'ref': ref_path,
                    'type': f'{ref_type}()',
                    'exists': exists,
                })

        # --- subprocess 脚本引用 ---
        for m in SCRIPT_REF_PATTERN.finditer(content):
            ref_path = m.group(1)
            line_num = content[:m.start()].count('\n') + 1
            exists = (root / ref_path).exists()

            key = (line_num, ref_path)
            if key not in seen_keys:
                seen_keys.add(key)
                findings.append({
                    'file': rel,
                    'line': line_num,
                    'ref': ref_path,
                    'type': 'subprocess',
                    'exists': exists,
                })

    return {'file_refs': findings}


def format_plain(data: dict) -> str:
    """将扫描结果格式化为纯文本"""
    refs = data.get('file_refs', [])
    if not refs:
        return ''
    lines = ["\n📄 文件引用:"]
    for entry in refs:
        status = "✓" if entry['exists'] else "✗"
        lines.append(
            f"  [{status}] {entry['file']}:{entry['line']} "
            f"→ {entry['ref']} ({entry['type']})"
        )
    return '\n'.join(lines)
