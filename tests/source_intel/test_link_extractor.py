# path: tests/source_intel/test_link_extractor.py
"""测试 LinkExtractor 链接提取器"""

from freeladder.source_intel.link_extractor import LinkExtractor
from freeladder.source_intel.models import SourceKind, SourceFormat


class TestLinkExtractor:
    def test_extract_markdown_links(self, link_extractor):
        text = """
        [订阅链接](https://raw.githubusercontent.com/test/repo/main/sub.txt)
        [Clash配置](https://example.com/clash.yaml)
        """
        sources = link_extractor.extract_from_text(text)
        assert len(sources) == 2
        urls = [s.url for s in sources]
        assert "https://raw.githubusercontent.com/test/repo/main/sub.txt" in urls
        assert "https://example.com/clash.yaml" in urls

    def test_extract_plain_urls(self, link_extractor):
        text = "访问 https://example.com/sub.txt 获取节点"
        sources = link_extractor.extract_from_text(text)
        assert len(sources) == 1
        assert sources[0].url == "https://example.com/sub.txt"

    def test_extract_html_links(self, link_extractor):
        html = '<a href="https://example.com/sub.txt">订阅</a>'
        sources = link_extractor.extract_from_html(html)
        assert len(sources) == 1
        assert sources[0].url == "https://example.com/sub.txt"

    def test_skip_javascript_urls(self, link_extractor):
        html = '<a href="javascript:void(0)">link</a>'
        sources = link_extractor.extract_from_html(html)
        assert len(sources) == 0

    def test_skip_mailto(self, link_extractor):
        html = '<a href="mailto:test@example.com">email</a>'
        sources = link_extractor.extract_from_html(html)
        assert len(sources) == 0

    def test_skip_localhost(self, link_extractor):
        text = "http://localhost:8080/sub.txt"
        sources = link_extractor.extract_from_text(text)
        assert len(sources) == 0

    def test_skip_private_ip(self, link_extractor):
        text = "http://192.168.1.1/sub.txt"
        sources = link_extractor.extract_from_text(text)
        assert len(sources) == 0

    def test_skip_10_x_ip(self, link_extractor):
        text = "http://10.0.0.1/sub.txt"
        sources = link_extractor.extract_from_text(text)
        assert len(sources) == 0

    def test_skip_onion(self, link_extractor):
        text = "http://example.onion/sub.txt"
        sources = link_extractor.extract_from_text(text)
        assert len(sources) == 0

    def test_normalize_url(self, link_extractor):
        url = link_extractor.normalize_url("https://example.com/sub.txt")
        assert url == "https://example.com/sub.txt"

    def test_normalize_relative_url(self, link_extractor):
        url = link_extractor.normalize_url("sub.txt", "https://example.com/path/")
        assert url == "https://example.com/path/sub.txt"

    def test_guess_kind_github_raw(self, link_extractor):
        kind = link_extractor.guess_kind("https://raw.githubusercontent.com/test/repo/main/sub.txt")
        assert kind == SourceKind.GITHUB_RAW

    def test_guess_kind_jsdelivr(self, link_extractor):
        kind = link_extractor.guess_kind("https://cdn.jsdelivr.net/gh/test/repo/sub.txt")
        assert kind == SourceKind.JSDELIVR

    def test_guess_kind_rss(self, link_extractor):
        kind = link_extractor.guess_kind("https://example.com/rss/feed.xml")
        assert kind == SourceKind.RSS

    def test_guess_format_clash(self, link_extractor):
        fmt = link_extractor.guess_format("https://example.com/clash.yaml")
        assert fmt == SourceFormat.CLASH

    def test_guess_format_base64(self, link_extractor):
        fmt = link_extractor.guess_format("https://example.com/base64/sub.txt")
        assert fmt == SourceFormat.BASE64

    def test_deduplication(self, link_extractor):
        text = """
        [link1](https://example.com/sub.txt)
        [link2](https://example.com/sub.txt)
        """
        sources = link_extractor.extract_from_text(text)
        assert len(sources) == 1

    def test_long_data_url_skipped(self, link_extractor):
        long_url = "data:text/plain;base64," + "A" * 20000
        sources = link_extractor.extract_from_text(long_url)
        assert len(sources) == 0

    def test_empty_text(self, link_extractor):
        sources = link_extractor.extract_from_text("")
        assert sources == []

    def test_direct_nodes(self, link_extractor):
        text = """
        vmess://eyJhZGQiOiIxMC4wLjAuMyJ9
        vless://uuid@10.0.0.4:443?security=tls#Test
        """
        nodes = link_extractor.extract_direct_nodes(text)
        assert len(nodes) == 2
        assert any("vmess://" in n for n in nodes)
        assert any("vless://" in n for n in nodes)
