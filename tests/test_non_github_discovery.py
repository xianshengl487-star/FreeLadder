# path: tests/test_non_github_discovery.py
"""测试非 GitHub 公开源候选发现

验证:
- SEED_PUBLIC_PAGES 存在且全部 enabled=False
- discover_from_sites 只扫描 enabled=True 的站点
- should_skip_url 过滤内网/私有地址
- fetch_page 有大小限制
"""

import pytest
from unittest.mock import patch, MagicMock

from freeladder.source_intel.non_github_discovery import (
    NonGitHubDiscovery,
    SEED_PUBLIC_PAGES,
    _BLOCKED_HOSTS,
)
from freeladder.source_intel.models import SourceRecord


class TestSeedPublicPages:
    def test_seed_pages_exist(self):
        assert len(SEED_PUBLIC_PAGES) >= 5

    def test_all_disabled_by_default(self):
        for page in SEED_PUBLIC_PAGES:
            assert page.get("enabled") is False, f"{page['name']} should be disabled"

    def test_each_page_has_required_fields(self):
        required = {"name", "url", "kind", "enabled", "note"}
        for page in SEED_PUBLIC_PAGES:
            assert required.issubset(page.keys()), f"{page} missing fields: {required - page.keys()}"

    def test_each_page_url_is_http(self):
        for page in SEED_PUBLIC_PAGES:
            assert page["url"].startswith("http"), f"{page['name']} URL must start with http"

    def test_get_seed_public_pages(self, source_store):
        from freeladder.source_intel.link_extractor import LinkExtractor
        discovery = NonGitHubDiscovery(source_store, extractor=LinkExtractor())
        pages = discovery.get_seed_public_pages()
        assert pages is SEED_PUBLIC_PAGES
        assert len(pages) >= 5


class TestDiscoverFromSites:
    def test_empty_sites_returns_empty(self, source_store):
        from freeladder.source_intel.link_extractor import LinkExtractor
        discovery = NonGitHubDiscovery(source_store, extractor=LinkExtractor())
        result = discovery.discover_from_sites([])
        assert result == []

    def test_all_disabled_returns_empty(self, source_store):
        from freeladder.source_intel.link_extractor import LinkExtractor
        discovery = NonGitHubDiscovery(source_store, extractor=LinkExtractor())
        sites = [
            {"name": "Test1", "url": "https://example.com", "enabled": False},
            {"name": "Test2", "url": "https://example2.com", "enabled": False},
        ]
        result = discovery.discover_from_sites(sites)
        assert result == []

    def test_only_enabled_sites_scanned(self, source_store):
        from freeladder.source_intel.link_extractor import LinkExtractor
        discovery = NonGitHubDiscovery(source_store, extractor=LinkExtractor())
        sites = [
            {"name": "Disabled", "url": "https://disabled.com", "enabled": False},
            {"name": "Enabled", "url": "https://enabled.com", "enabled": True},
        ]
        with patch.object(discovery, 'fetch_page', return_value='<a href="https://example.com/sub.txt">link</a>') as mock_fetch:
            discovery.discover_from_sites(sites)
            mock_fetch.assert_called_once_with("https://enabled.com")

    def test_cancel_token_stops_early(self, source_store):
        from freeladder.source_intel.link_extractor import LinkExtractor
        from freeladder.core.cancel_token import CancelToken
        discovery = NonGitHubDiscovery(source_store, extractor=LinkExtractor())
        token = CancelToken()
        token.cancel()
        sites = [{"name": "Test", "url": "https://example.com", "enabled": True}]
        result = discovery.discover_from_sites(sites, cancel_token=token)
        assert result == []

    def test_progress_callback_called(self, source_store):
        from freeladder.source_intel.link_extractor import LinkExtractor
        discovery = NonGitHubDiscovery(source_store, extractor=LinkExtractor())
        sites = [{"name": "Test", "url": "https://example.com", "enabled": True}]
        progress_calls = []
        with patch.object(discovery, 'fetch_page', return_value=''):
            discovery.discover_from_sites(sites, on_progress=lambda i, t, m: progress_calls.append((i, t, m)))
            assert len(progress_calls) == 1
            assert progress_calls[0][0] == 1


class TestShouldSkipUrl:
    def test_skip_localhost(self, source_store):
        from freeladder.source_intel.link_extractor import LinkExtractor
        discovery = NonGitHubDiscovery(source_store, extractor=LinkExtractor())
        assert discovery.should_skip_url("http://localhost:8080/sub.txt") is True

    def test_skip_loopback(self, source_store):
        from freeladder.source_intel.link_extractor import LinkExtractor
        discovery = NonGitHubDiscovery(source_store, extractor=LinkExtractor())
        assert discovery.should_skip_url("http://127.0.0.1/sub.txt") is True

    def test_skip_private_10(self, source_store):
        from freeladder.source_intel.link_extractor import LinkExtractor
        discovery = NonGitHubDiscovery(source_store, extractor=LinkExtractor())
        assert discovery.should_skip_url("http://10.0.0.1/sub.txt") is True

    def test_skip_private_192(self, source_store):
        from freeladder.source_intel.link_extractor import LinkExtractor
        discovery = NonGitHubDiscovery(source_store, extractor=LinkExtractor())
        assert discovery.should_skip_url("http://192.168.1.1/sub.txt") is True

    def test_skip_private_172(self, source_store):
        from freeladder.source_intel.link_extractor import LinkExtractor
        discovery = NonGitHubDiscovery(source_store, extractor=LinkExtractor())
        assert discovery.should_skip_url("http://172.16.0.1/sub.txt") is True

    def test_skip_onion(self, source_store):
        from freeladder.source_intel.link_extractor import LinkExtractor
        discovery = NonGitHubDiscovery(source_store, extractor=LinkExtractor())
        assert discovery.should_skip_url("http://example.onion/sub.txt") is True

    def test_skip_ftp(self, source_store):
        from freeladder.source_intel.link_extractor import LinkExtractor
        discovery = NonGitHubDiscovery(source_store, extractor=LinkExtractor())
        assert discovery.should_skip_url("ftp://example.com/sub.txt") is True

    def test_allow_public_https(self, source_store):
        from freeladder.source_intel.link_extractor import LinkExtractor
        discovery = NonGitHubDiscovery(source_store, extractor=LinkExtractor())
        assert discovery.should_skip_url("https://example.com/sub.txt") is False

    def test_invalid_url(self, source_store):
        from freeladder.source_intel.link_extractor import LinkExtractor
        discovery = NonGitHubDiscovery(source_store, extractor=LinkExtractor())
        assert discovery.should_skip_url("not a url at all") is True
