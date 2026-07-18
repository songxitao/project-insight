"""
端口与 URL 硬编码扫描模块 — 从代码中提取硬编码的端口、URL 和 IP 地址。

用法:
    from extractors.urls import run
    result = run("/path/to/project")
"""

import re
from pathlib import Path


PORT_PATTERN = re.compile(r"(?:port|PORT)\s*[=:]\s*(\d{4,5})")
LOCALHOST_PORT_PATTERN = re.compile(r"localhost:(\d{4,5})")
ZERO_HOST_PORT_PATTERN = re.compile(r"0\.0\.0\.0:(\d{4,5})")
URL_PATTERN = re.compile(
    r"""['\"]((https?://(?!example\.com|schemas\.)[^'\"\\s]+))['\"]"""
)
IP_PATTERN = re.compile(r"(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})")


def _is_url_blacklisted(url: str) -> bool:
    """检查 URL 是否为常见的库/框架默认 URL"""
    blacklist = {
        'https://pypi.org',
        'https://pypi.python.org',
        'https://files.pythonhosted.org',
        'https://github.com',
        'https://raw.githubusercontent.com',
        'https://registry.npmjs.org',
    }
    return any(url.startswith(b) for b in blacklist)


def _scan_file(filepath: str, rel: str) -> dict:
    """扫描单个文件中的端口/URL/IP"""
    try:
        content = Path(filepath).read_text(encoding='utf-8', errors='replace')
    except Exception:
        return {}

    result = {}

    ports = [int(m.group(1)) for m in PORT_PATTERN.finditer(content)]
    if ports:
        result['ports'] = list(set(ports))

    localhost_ports = [int(m.group(1)) for m in LOCALHOST_PORT_PATTERN.finditer(content)]
    if localhost_ports:
        result['localhost_ports'] = list(set(localhost_ports))

    zero_host_ports = [int(m.group(1)) for m in ZERO_HOST_PORT_PATTERN.finditer(content)]
    if zero_host_ports:
        result['zero_host_ports'] = list(set(zero_host_ports))

    urls = [m.group(1) for m in URL_PATTERN.finditer(content)
            if not _is_url_blacklisted(m.group(1))]
    if urls:
        result['urls'] = list(set(urls))

    ips = [m.group(1) for m in IP_PATTERN.finditer(content)]
    if ips:
        result['ips'] = list(set(ips))

    return result


def _is_skip_dirs(p: Path) -> bool:
    skip = {'__pycache__', '.git', 'venv', '.venv', 'env',
            'node_modules', 'build', 'dist', '.pytest_cache',
            '.ruff_cache', '.workbuddy', 'output', 'testset',
            '.pilot_venv', '.superpowers', '.agents', '.claude',
            '.scratch'}
    return any(part.name in skip for part in p.parents)


def run(root_dir: str) -> dict:
    """提取项目中的硬编码端口、URL 和 IP 地址"""
    root = Path(root_dir)
    findings = []
    all_ports = set()
    all_urls = set()
    all_ips = set()

    for f in sorted(root.rglob('*')):
        if not f.is_file():
            continue
        if _is_skip_dirs(f):
            continue

        ext = f.suffix.lower()
        if ext not in ('.py', '.bat', '.sh', '.ps1', '.yaml', '.yml',
                       '.json', '.toml', '.cfg', '.ini', '.env', '.conf'):
            continue

        rel = str(f.relative_to(root))
        result = _scan_file(str(f), rel)
        if result:
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
