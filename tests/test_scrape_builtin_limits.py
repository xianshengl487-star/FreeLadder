# path: tests/test_scrape_builtin_limits.py
"""scrape_builtin 限流和取消测试

验证:
- max_total_nodes 限制
- cancel_token 取消
- 失败源缓存
- 并发执行
"""

import time
from unittest.mock import MagicMock, patch

import pytest

from freeladder.core.cancel_token import CancelToken
from freeladder.core.config import Config, ScraperConfig
from freeladder.core.models import Node, Protocol


def _fake_scrape_source(url, timeout=15):
    """模拟爬取，返回固定节点"""
    return [
        Node(
            node_key=f"vmess:{url}:{i}",
            protocol=Protocol.VMESS,
            server=f"10.0.{i // 256}.{i % 256}",
            port=443,
            raw_uri=f"vmess://{url}:{i}",
        )
        for i in range(10)
    ]


_FAKE_SOURCES = [
    {"name": f"src{i}", "url": f"http://example{i}.com/sub", "format": "base64"}
    for i in range(10)
]


class TestScrapeBuiltinLimits:
    def test_max_total_nodes(self):
        """max_total_nodes 限制总节点数"""
        from freeladder.scraper.scraper import scrape_builtin

        with patch("freeladder.scraper.scraper.scrape_source", side_effect=_fake_scrape_source):
            with patch("freeladder.scraper.scraper.get_config") as mock_cfg:
                cfg = Config(scraper=ScraperConfig(
                    max_workers=2,
                    max_nodes_per_source=100,
                    max_total_nodes=25,
                    source_failure_cache_minutes=60,
                    builtin_enabled=True,
                ))
                mock_cfg.return_value = cfg
                with patch("freeladder.core.builtin_sources.BUILTIN_SOURCES", _FAKE_SOURCES):
                    nodes = scrape_builtin(max_total_nodes=25)
                    assert len(nodes) <= 25

    def test_cancel_token_stops_scraping(self):
        """cancel_token 取消爬取"""
        from freeladder.scraper.scraper import scrape_builtin

        def slow_scrape(url, timeout=15):
            time.sleep(0.1)
            return [
                Node(
                    node_key=f"vmess:{url}:0",
                    protocol=Protocol.VMESS,
                    server="10.0.0.1",
                    port=443,
                    raw_uri=f"vmess://{url}",
                )
            ]

        token = CancelToken()
        token.cancel()

        with patch("freeladder.scraper.scraper.scrape_source", side_effect=slow_scrape):
            with patch("freeladder.scraper.scraper.get_config") as mock_cfg:
                cfg = Config(scraper=ScraperConfig(
                    max_workers=2,
                    max_nodes_per_source=100,
                    max_total_nodes=8000,
                    source_failure_cache_minutes=60,
                    builtin_enabled=True,
                ))
                mock_cfg.return_value = cfg
                with patch("freeladder.core.builtin_sources.BUILTIN_SOURCES", _FAKE_SOURCES[:5]):
                    nodes = scrape_builtin(cancel_token=token)
                    assert len(nodes) == 0

    def test_max_nodes_per_source(self):
        """max_nodes_per_source 限制单源节点数"""
        from freeladder.scraper.scraper import scrape_builtin

        def big_source(url, timeout=15):
            return [
                Node(
                    node_key=f"vmess:{url}:{i}",
                    protocol=Protocol.VMESS,
                    server=f"10.0.{i // 256}.{i % 256}",
                    port=443,
                    raw_uri=f"vmess://{url}:{i}",
                )
                for i in range(200)
            ]

        with patch("freeladder.scraper.scraper.scrape_source", side_effect=big_source):
            with patch("freeladder.scraper.scraper.get_config") as mock_cfg:
                cfg = Config(scraper=ScraperConfig(
                    max_workers=1,
                    max_nodes_per_source=50,
                    max_total_nodes=8000,
                    source_failure_cache_minutes=60,
                    builtin_enabled=True,
                ))
                mock_cfg.return_value = cfg
                with patch("freeladder.core.builtin_sources.BUILTIN_SOURCES", [
                    {"name": "src1", "url": "http://example.com/sub", "format": "base64"},
                ]):
                    nodes = scrape_builtin()
                    assert len(nodes) <= 50

    def test_builtin_disabled(self):
        """builtin_enabled=false 时返回空"""
        from freeladder.scraper.scraper import scrape_builtin

        with patch("freeladder.scraper.scraper.get_config") as mock_cfg:
            cfg = Config(scraper=ScraperConfig(builtin_enabled=False))
            mock_cfg.return_value = cfg
            nodes = scrape_builtin()
            assert nodes == []

    def test_concurrent_execution(self):
        """验证并发爬取确实并行执行"""
        from freeladder.scraper.scraper import scrape_builtin

        call_times = []

        def timed_scrape(url, timeout=15):
            call_times.append((url, time.time()))
            time.sleep(0.05)
            return [
                Node(
                    node_key=f"vmess:{url}:0",
                    protocol=Protocol.VMESS,
                    server="10.0.0.1",
                    port=443,
                    raw_uri=f"vmess://{url}",
                )
            ]

        with patch("freeladder.scraper.scraper.scrape_source", side_effect=timed_scrape):
            with patch("freeladder.scraper.scraper.get_config") as mock_cfg:
                cfg = Config(scraper=ScraperConfig(
                    max_workers=4,
                    max_nodes_per_source=100,
                    max_total_nodes=8000,
                    source_failure_cache_minutes=60,
                    builtin_enabled=True,
                ))
                mock_cfg.return_value = cfg
                with patch("freeladder.core.builtin_sources.BUILTIN_SOURCES", _FAKE_SOURCES[:8]):
                    t0 = time.time()
                    nodes = scrape_builtin()
                    elapsed = time.time() - t0
                    # With 4 workers and 8 sources of 50ms each, should take ~100ms not ~400ms
                    assert elapsed < 0.3
