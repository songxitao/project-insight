"""
集中管理纯正则 extractor — urls/paths/entries/file_refs 的统一入口。

提供 ScanPattern dataclass + REGEX_PATTERNS 配置表，
以及各 category 独立的 run_* 函数和通用的 format_plain 分发器。

用法:
    from extractors.patterns import run_urls, run_paths, format_plain
    result = run_urls("/path/to/project")
    print(format_plain(result))
"""

import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

from . import iter_project_files, safe_read


# ---------------------------------------------------------------------------
# ScanPattern dataclass
# ---------------------------------------------------------------------------

@dataclass
class ScanPattern:
    """单个正则扫描模式的定义"""
    name: str
    pattern: re.Pattern
    module: str          # 所属模块名："urls" / "paths" / "entries" / "file_refs"
    category: str        # 输出 JSON 中的 key
    known_false_positives: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# REGEX_PATTERNS — 四类正则配置表
# ---------------------------------------------------------------------------

REGEX_PATTERNS: dict[str, list[ScanPattern]] = {
    "urls": [
        ScanPattern(
            name="PORT",
            pattern=re.compile(r"(?:port|PORT)\s*[=:]\s*(\d{4,5})"),
            module="urls",
            category="ports",
            known_false_positives=[],
        ),
        ScanPattern(
            name="LOCALHOST_PORT",
            pattern=re.compile(r"localhost:(\d{4,5})"),
            module="urls",
            category="localhost_ports",
        ),
        ScanPattern(
            name="ZERO_HOST_PORT",
            pattern=re.compile(r"0\.0\.0\.0:(\d{4,5})"),
            module="urls",
            category="zero_host_ports",
        ),
        ScanPattern(
            name="URL",
            pattern=re.compile(
                r"""['\"]((https?://(?!example\.com|schemas\.)[^'\"\\s]+))['\"]"""
            ),
            module="urls",
            category="urls",
            known_false_positives=[
                "https://pypi.org",
                "https://github.com",
            ],
        ),
        ScanPattern(
            name="IP",
            pattern=re.compile(r"(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})"),
            module="urls",
            category="ips",
        ),
    ],
    "paths": [
        ScanPattern(
            name="PATH",
            pattern=re.compile(
                r'(?:sys\.path\.insert|sys\.path\.append|PYTHONPATH|PATH=)'
                r'[\s\(]*[\'"]?([a-zA-Z]:[\\/][^\'")\s]+)[\'"]?',
            ),
            module="paths",
            category="paths",
        ),
    ],
    "entries": [
        ScanPattern(
            name="ENTRY_PATTERNS",
            pattern=re.compile(r"if\s+__name__\s*==\s*['\"]__main__['\"]"),
            module="entries",
            category="entry_points",
        ),
        ScanPattern(
            name="ENTRY_PATTERNS",
            pattern=re.compile(r"app\s*=\s*(?:FastAPI|Flask|Sanic|Django)\s*\("),
            module="entries",
            category="entry_points",
        ),
        ScanPattern(
            name="ENTRY_PATTERNS",
            pattern=re.compile(r"typer\.run\(|cli\.command|@click\.command"),
            module="entries",
            category="entry_points",
        ),
        ScanPattern(
            name="ENTRY_PATTERNS",
            pattern=re.compile(r"uvicorn\.run\(|gunicorn"),
            module="entries",
            category="entry_points",
        ),
        ScanPattern(
            name="API_PATTERN",
            pattern=re.compile(
                r"@(?:app|router|api)\.(?:get|post|put|delete|patch|route|websocket)"
                r"\s*\(\s*['\"](.+?)['\"]"
            ),
            module="entries",
            category="api_endpoints",
        ),
    ],
    "file_refs": [
        ScanPattern(
            name="QUOTED_REF",
            pattern=re.compile(
                r"""(?P<type>(?:pathlib\.)?Path|open)\s*\(\s*["'](?P<path>[^"']+)["']\s*\)"""
            ),
            module="file_refs",
            category="quoted_refs",
        ),
        ScanPattern(
            name="SCRIPT_REF",
            pattern=re.compile(
                r"""(?:subprocess\.\w+|subprocess)\s*\([^)]*?["']([^"']+\.(?:
                    py|sh|bat|ps1))["']""",
                re.VERBOSE,
            ),
            module="file_refs",
            category="script_refs",
        ),
    ],
}


# ---------------------------------------------------------------------------
# 通用 URL 黑名单
# ---------------------------------------------------------------------------

URL_BLACKLIST = frozenset({
    'https://pypi.org',
    'https://pypi.python.org',
    'https://files.pythonhosted.org',
    'https://github.com',
    'https://raw.githubusercontent.com',
    'https://registry.npmjs.org',
})


def _is_url_blacklisted(url: str) -> bool:
    """检查 URL 是否为常见的库/框架默认 URL"""
    return any(url.startswith(b) for b in URL_BLACKLIST)


# ---------------------------------------------------------------------------
# 文件引用扩展名白名单
# ---------------------------------------------------------------------------

ALLOWED_EXTS = frozenset({
    '.py', '.json', '.yaml', '.yml', '.csv', '.txt',
    '.md', '.toml', '.cfg', '.ini', '.conf', '.xml',
})


def _has_allowed_ext(path_str: str) -> bool:
    """检查文件路径是否有允许的扩展名"""
    return Path(path_str).suffix.lower() in ALLOWED_EXTS


# ---------------------------------------------------------------------------
# entries 辅助函数
# ---------------------------------------------------------------------------

def _read_snippet(filepath: str) -> str:
    """只读前 200 行和末尾 20 行"""
    try:
        with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
            lines = f.readlines()
    except Exception:
        return ''

    total = len(lines)
    if total <= 220:
        return ''.join(lines)

    head = ''.join(lines[:200])
    tail = ''.join(lines[-20:])
    return head + '\n# ... (skipped middle) ...\n' + tail


def _get_context_lines(lines: list, idx: int, max_lines: int, context: int = 2) -> str:
    """提取匹配行上下的上下文"""
    start = max(0, idx - context)
    end = min(max_lines, idx + context + 1)
    return '\n'.join(lines[start:end])


# ---------------------------------------------------------------------------
# run_urls — 硬编码端口/URL/IP 扫描
# ---------------------------------------------------------------------------

def run_urls(root_dir: str) -> dict:
    """提取项目中的硬编码端口、URL 和 IP 地址"""
    root = Path(root_dir)
    findings = []
    all_ports = set()
    all_urls = set()
    all_ips = set()

    # 提取预编译正则
    port_re = REGEX_PATTERNS["urls"][0].pattern     # PORT
    localhost_re = REGEX_PATTERNS["urls"][1].pattern # LOCALHOST_PORT
    zero_host_re = REGEX_PATTERNS["urls"][2].pattern # ZERO_HOST_PORT
    url_re = REGEX_PATTERNS["urls"][3].pattern        # URL
    ip_re = REGEX_PATTERNS["urls"][4].pattern         # IP

    extensions = ('.py', '.bat', '.sh', '.ps1', '.yaml', '.yml',
                  '.json', '.toml', '.cfg', '.ini', '.env', '.conf')
    for rel_f in iter_project_files(root, extensions=extensions):
        f = root / rel_f
        try:
            content = Path(str(f)).read_text(encoding='utf-8', errors='replace')
        except Exception:
            continue

        rel = str(rel_f)
        result = {}

        ports = [int(m.group(1)) for m in port_re.finditer(content)]
        if ports:
            result['ports'] = list(set(ports))

        localhost_ports = [int(m.group(1)) for m in localhost_re.finditer(content)]
        if localhost_ports:
            result['localhost_ports'] = list(set(localhost_ports))

        zero_host_ports = [int(m.group(1)) for m in zero_host_re.finditer(content)]
        if zero_host_ports:
            result['zero_host_ports'] = list(set(zero_host_ports))

        urls = [m.group(1) for m in url_re.finditer(content)
                if not _is_url_blacklisted(m.group(1))]
        if urls:
            result['urls'] = list(set(urls))

        ips = [m.group(1) for m in ip_re.finditer(content)]
        if ips:
            result['ips'] = list(set(ips))

        if not result:
            continue

        entry = {'file': rel}
        if 'ports' in result:
            entry['ports'] = result['ports']
            all_ports.update(result['ports'])
        if 'localhost_ports' in result:
            entry['localhost_ports'] = result['localhost_ports']
            all_ports.update(result['localhost_ports'])
        if 'zero_host_ports' in result:
            entry['zero_host_ports'] = result['zero_host_ports']
            all_ports.update(result['zero_host_ports'])
        if 'urls' in result:
            entry['urls'] = result['urls']
            all_urls.update(result['urls'])
        if 'ips' in result:
            entry['ips'] = result['ips']
            all_ips.update(result['ips'])
        findings.append(entry)

    return {
        'hardcoded_urls': findings,
        'hardcoded_urls_summary': {
            'unique_ports': sorted(all_ports),
            'unique_urls': sorted(all_urls),
            'unique_ips': sorted(all_ips),
        },
    }


# ---------------------------------------------------------------------------
# run_paths — 本地硬编码路径扫描
# ---------------------------------------------------------------------------

def run_paths(root_dir: str) -> dict:
    """扫描项目中所有硬编码的本地路径"""
    root = Path(root_dir)
    path_re = REGEX_PATTERNS["paths"][0].pattern  # PATH
    result = []

    for rel_f in iter_project_files(root, extensions=None):
        f = root / rel_f
        ext = f.suffix.lower()
        if ext in ('.py', '.bat', '.sh', '.ps1') or \
           f.name.lower() in ('dockerfile', 'dockerfile.dev', 'dockerfile.prod'):
            try:
                content = Path(str(f)).read_text(encoding='utf-8', errors='replace')
            except Exception:
                continue
            paths = [m.group(1) for m in path_re.finditer(content)]
            if paths:
                result.append({
                    'file': str(rel_f),
                    'paths': paths
                })

    return {'local_paths': result}


# ---------------------------------------------------------------------------
# run_entries — 入口点与 API 端点提取
# ---------------------------------------------------------------------------

def run_entries(root_dir: str) -> dict:
    """提取项目的入口点和 API 端点"""
    root = Path(root_dir)
    entry_points = []
    api_endpoints = []

    # 入口点模式: (pattern, entry_type)
    ENTRY_PATTERNS_TYPES = [
        (REGEX_PATTERNS["entries"][0].pattern, 'main_guard'),
        (REGEX_PATTERNS["entries"][1].pattern, 'web_framework'),
        (REGEX_PATTERNS["entries"][2].pattern, 'cli_tool'),
        (REGEX_PATTERNS["entries"][3].pattern, 'server_launcher'),
    ]
    API_PATTERN = REGEX_PATTERNS["entries"][4].pattern

    for rel_f in iter_project_files(root, extensions=('.py',)):
        f = root / rel_f
        snippet = _read_snippet(str(f))
        if not snippet:
            continue

        lines = snippet.split('\n')
        rel = str(rel_f)

        # 匹配入口点
        for pattern, entry_type in ENTRY_PATTERNS_TYPES:
            for i, line in enumerate(lines):
                stripped_line = line.strip()
                if stripped_line.startswith('re.compile(') or \
                   stripped_line.startswith('(re.compile(') or \
                   'ENTRY_PATTERNS' in stripped_line or \
                   'PATTERN' in stripped_line:
                    continue
                if pattern.search(line):
                    ctx = _get_context_lines(lines, i, len(lines))
                    entry_points.append({
                        'file': rel,
                        'type': entry_type,
                        'line': i + 1,
                        'context': ctx,
                    })

        # 匹配 API 端点
        for i, line in enumerate(lines):
            m = API_PATTERN.search(line)
            if m:
                ctx = _get_context_lines(lines, i, len(lines))
                api_endpoints.append({
                    'file': rel,
                    'route': m.group(1),
                    'line': i + 1,
                    'context': ctx,
                })

    return {
        'entry_points': entry_points,
        'api_endpoints': api_endpoints,
    }


# ---------------------------------------------------------------------------
# run_file_refs — 文件引用扫描
# ---------------------------------------------------------------------------

def run_file_refs(root_dir: str) -> dict:
    """提取项目中的文件引用"""
    root = Path(root_dir)
    quoted_re = REGEX_PATTERNS["file_refs"][0].pattern   # QUOTED_REF
    script_re = REGEX_PATTERNS["file_refs"][1].pattern   # SCRIPT_REF
    findings = []

    for rel_f in iter_project_files(root, extensions=('.py',)):
        f = root / rel_f
        content = safe_read(str(f))
        if not content:
            continue

        rel = str(rel_f)
        seen_keys = set()

        # --- Path() / open() ---
        for m in quoted_re.finditer(content):
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
        for m in script_re.finditer(content):
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


# ---------------------------------------------------------------------------
# format_plain — 自动分发格式化器
# ---------------------------------------------------------------------------

def format_plain(data: dict) -> str:
    """根据 data 中出现的 key 自动分发到对应 category 的格式化逻辑"""
    if 'hardcoded_urls' in data:
        return _format_urls(data)
    elif 'local_paths' in data:
        return _format_paths(data)
    elif 'entry_points' in data or 'api_endpoints' in data:
        return _format_entries(data)
    elif 'file_refs' in data:
        return _format_file_refs(data)
    return ''


def _format_urls(data: dict) -> str:
    """格式化硬编码 URL/端口/IP 展示"""
    lines = []
    refs = data.get('hardcoded_urls', [])

    field_labels = {
        'ports': '端口',
        'localhost_ports': 'localhost',
        'zero_host_ports': '0.0.0.0',
        'urls': 'URL',
        'ips': 'IP',
    }

    lines.append(f"\n🔗 硬编码 URL/端口/IP ({len(refs)} 个文件):")
    for entry in refs:
        lines.append(f"  {entry['file']}")
        for key, label in field_labels.items():
            values = entry.get(key)
            if values:
                lines.append(f"    └─ {label}: {values}")
    return '\n'.join(lines)


def _format_paths(data: dict) -> str:
    """将扫描结果格式化为纯文本"""
    local_paths = data.get('local_paths', [])
    if not local_paths:
        return ''
    lines = ["\n⚠️  本地路径硬编码:"]
    for s in local_paths:
        for p in s['paths']:
            lines.append(f"  {s['file']} → {p}")
    return '\n'.join(lines)


def _format_entries(data: dict) -> str:
    """将入口点与 API 端点格式化为纯文本摘要"""
    lines = []
    eps = data.get('entry_points', [])
    apis = data.get('api_endpoints', [])

    if eps:
        lines.append(f"\n🚪 入口点 ({len(eps)} 个):")
        for ep in eps:
            lines.append(f"  [{ep['type']}] {ep['file']}:{ep['line']}")
            lines.append(f"    └─ {ep['context'][:80]}...")

    if apis:
        lines.append(f"\n🌐 API 端点 ({len(apis)} 个):")
        for ep in apis:
            lines.append(f"  {ep['route']}  ({ep['file']}:{ep['line']})")

    return '\n'.join(lines)


def _format_file_refs(data: dict) -> str:
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


# ---------------------------------------------------------------------------
# EXTRA_REGISTRY — 供 __init__.py 的 REGISTRY 扩展
# ---------------------------------------------------------------------------

_this_mod = sys.modules[__name__]

EXTRA_REGISTRY: dict[str, dict] = {
    'urls':     {'run': run_urls,     'mod': _this_mod},
    'paths':    {'run': run_paths,    'mod': _this_mod},
    'entries':  {'run': run_entries,  'mod': _this_mod},
    'file_refs': {'run': run_file_refs, 'mod': _this_mod},
}
