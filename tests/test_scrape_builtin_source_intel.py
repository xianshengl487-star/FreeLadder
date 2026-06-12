# path: tests/test_scrape_builtin_source_intel.py
"""测试 scrape_builtin 集成 source_intel

验证:
- scrape_builtin 在没有 enabled source 且 builtin_enabled=false 时返回空
- scrape_builtin 只使用 source_intel enabled 源
- scrape_builtin 在 builtin_enabled=true 时追加 legacy 源
- 失败源缓存正常工作
"""

import time
import pytest
from unittest.mock import patch, MagicMock

from freeladder.scraper.scraper import _failure_cache, _is_source_failed, _mark_source_failed


class TestScrapeBuiltinSourceIntel:
    def test_no_sources_returns_empty(self):
        """没有启用源且 builtin_enabled=false 时返回空"""
        with patch("freeladder.scraper.scraper.get_config") as mock_config:
            mock_cfg = MagicMock()
            mock_cfg.scraper.builtin_enabled = False
            mock_cfg.scraper.max_total_nodes = 8000
            mock_cfg.source_intel.enabled = True
            mock_config.return_value = mock_cfg

            with patch("freeladder.source_intel.engine.SourceIntelEngine") as MockEngine:
                instance = MagicMock()
                instance.get_enabled_source_urls.return_value = []
                MockEngine.return_value = instance

                from freeladder.scraper.scraper import scrape_builtin
                result = scrape_builtin()
                assert result == []

    def test_only_source_intel_enabled(self):
        """builtin_enabled=false 时只使用 source_intel enabled 源"""
        with patch("freeladder.scraper.scraper.get_config") as mock_config:
            mock_cfg = MagicMock()
            mock_cfg.scraper.builtin_enabled = False
            mock_cfg.scraper.max_total_nodes = 8000
            mock_cfg.scraper.request_timeout = 10
            mock_cfg.scraper.max_workers = 2
            mock_cfg.scraper.source_failure_cache_minutes = 60
            mock_cfg.scraper.max_nodes_per_source = 800
            mock_cfg.source_intel.enabled = True
            mock_config.return_value = mock_cfg

            with patch("freeladder.source_intel.engine.SourceIntelEngine") as MockEngine:
                instance = MagicMock()
                instance.get_enabled_source_urls.return_value = ["https://example.com/si-sub.txt"]
                MockEngine.return_value = instance

                with patch("freeladder.scraper.scraper.scrape_source", return_value=[]) as mock_scrape:
                    with patch("freeladder.scraper.scraper.deduplicate_nodes", return_value=[]):
                        from freeladder.scraper.scraper import scrape_builtin
                        result = scrape_builtin()
                        # Should have tried to scrape the source_intel URL
                        mock_scrape.assert_called_once()
                        call_url = mock_scrape.call_args[0][0]
                        assert call_url == "https://example.com/si-sub.txt"

    def test_builtin_enabled_appends_legacy(self):
        """builtin_enabled=true 时追加 legacy 源"""
        with patch("freeladder.scraper.scraper.get_config") as mock_config:
            mock_cfg = MagicMock()
            mock_cfg.scraper.builtin_enabled = True
            mock_cfg.scraper.max_total_nodes = 8000
            mock_cfg.scraper.request_timeout = 10
            mock_cfg.scraper.max_workers = 2
            mock_cfg.scraper.source_failure_cache_minutes = 60
            mock_cfg.scraper.max_nodes_per_source = 800
            mock_cfg.source_intel.enabled = True
            mock_config.return_value = mock_cfg

            with patch("freeladder.source_intel.engine.SourceIntelEngine") as MockEngine:
                instance = MagicMock()
                instance.get_enabled_source_urls.return_value = ["https://si.example.com/sub"]
                MockEngine.return_value = instance

                with patch("freeladder.scraper.scraper.scrape_source", return_value=[]) as mock_scrape:
                    with patch("freeladder.scraper.scraper.deduplicate_nodes", return_value=[]):
                        with patch("freeladder.core.builtin_sources.BUILTIN_SOURCES", [{"url": "https://legacy.example.com/sub"}]):
                            from freeladder.scraper.scraper import scrape_builtin
                            result = scrape_builtin()
                            # scrape_source should be called twice: SI + legacy
                            assert mock_scrape.call_count == 2

    def test_source_intel_exception_fallback(self):
        """source_intel 加载异常时只用 legacy"""
        with patch("freeladder.scraper.scraper.get_config") as mock_config:
            mock_cfg = MagicMock()
            mock_cfg.scraper.builtin_enabled = True
            mock_cfg.scraper.max_total_nodes = 8000
            mock_cfg.scraper.request_timeout = 10
            mock_cfg.scraper.max_workers = 2
            mock_cfg.scraper.source_failure_cache_minutes = 60
            mock_cfg.scraper.max_nodes_per_source = 800
            mock_cfg.source_intel.enabled = True
            mock_config.return_value = mock_cfg

            with patch("freeladder.source_intel.engine.SourceIntelEngine", side_effect=ImportError("no module")):
                with patch("freeladder.scraper.scraper.scrape_source", return_value=[]) as mock_scrape:
                    with patch("freeladder.scraper.scraper.deduplicate_nodes", return_value=[]):
                        with patch("freeladder.core.builtin_sources.BUILTIN_SOURCES", [{"url": "https://legacy.example.com/sub"}]):
                            from freeladder.scraper.scraper import scrape_builtin
                            result = scrape_builtin()
                            assert mock_scrape.call_count == 1


class TestFailureCache:
    def setup_method(self):
        _failure_cache.clear()

    def test_mark_and_check(self):
        _mark_source_failed("https://example.com/bad")
        assert _is_source_failed("https://example.com/bad", cache_minutes=60) is True

    def test_cache_expiry(self):
        _failure_cache["https://example.com/expired"] = time.time() - 7200  # 2 hours ago
        assert _is_source_failed("https://example.com/expired", cache_minutes=60) is False

    def test_not_in_cache(self):
        assert _is_source_failed("https://example.com/unknown", cache_minutes=60) is False
