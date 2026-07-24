import pytest
pytestmark = pytest.mark.skip(reason="v0.5.0 正则坍缩到 patterns.py，旧测试存档")

"""
Tests for urls.py — hardcoded URL, port & IP scanning.
"""
from extractors.urls import run


def test_empty_project(tmp_project):
    """空项目 → hardcoded_urls 为空列表"""
    result = run(str(tmp_project))
    assert result["hardcoded_urls"] == []


def test_port_assignment(tmp_project):
    """port=8080 可提取端口号"""
    (tmp_project / "config.yaml").write_text("port=8080\n", encoding="utf-8")
    result = run(str(tmp_project))
    assert 8080 in result["hardcoded_urls"][0]["ports"]


def test_localhost_port(tmp_project):
    """localhost:3000 可提取端口号"""
    (tmp_project / "config.yaml").write_text(
        'url = "http://localhost:3000/api"\n', encoding="utf-8"
    )
    result = run(str(tmp_project))
    assert 3000 in result["hardcoded_urls"][0]["localhost_ports"]


def test_blacklist_filtered(tmp_project):
    """example.com 被黑名单过滤，不出现在结果中"""
    (tmp_project / "config.yaml").write_text(
        'url = "http://example.com/test"\n', encoding="utf-8"
    )
    result = run(str(tmp_project))
    assert result["hardcoded_urls"] == []


def test_custom_url_extracted(tmp_project):
    """非黑名单的自定义 URL 被正确提取"""
    (tmp_project / "config.yaml").write_text(
        'url = "http://myapi.internal/v1/data"\n', encoding="utf-8"
    )
    result = run(str(tmp_project))
    assert "http://myapi.internal/v1/data" in result["hardcoded_urls"][0]["urls"]


def test_ip_address_extracted(tmp_project):
    """IP 地址被正确提取"""
    (tmp_project / "config.yaml").write_text(
        'host = "192.168.1.1"\n', encoding="utf-8"
    )
    result = run(str(tmp_project))
    assert "192.168.1.1" in result["hardcoded_urls"][0]["ips"]


def test_skip_dirs_ignored(tmp_project):
    """跳过目录中的文件不参与扫描"""
    skip_dir = tmp_project / ".venv"
    skip_dir.mkdir(parents=True)
    (skip_dir / "config.yaml").write_text("port=8080\n", encoding="utf-8")
    result = run(str(tmp_project))
    assert result["hardcoded_urls"] == []


def test_summary_dedup(tmp_project):
    """hardcoded_urls_summary 中去重正确"""
    (tmp_project / "a.yaml").write_text(
        'host = "10.0.0.1"\n', encoding="utf-8"
    )
    (tmp_project / "b.yaml").write_text(
        'host = "10.0.0.1"\n', encoding="utf-8"
    )
    result = run(str(tmp_project))
    assert result["hardcoded_urls_summary"]["unique_ips"] == ["10.0.0.1"]
