# path: tests/test_fetch_pipeline.py
"""测试 FetchPipeline

覆盖:
- 没有 enabled source 时返回空
- FetchPipeline 不无限提交 future
- FetchPipeline 支持 cancel_token
- 统计返回正确
"""

import pytest
from unittest.mock import patch, MagicMock

from freeladder.core.cancel_token import CancelToken
from freeladder.tasks.fetch_pipeline import run_fetch_pipeline


def _make_mock_config(tmp_path):
    cfg = MagicMock()
    cfg.performance.fetch_workers = 2
    cfg.performance.db_batch_size = 100
    cfg.performance.db_queue_max_size = 100
    cfg.performance.max_pending_futures = 10
    cfg.performance.max_total_nodes_per_task = 10000
    cfg.performance.max_nodes_per_source = 1000
    cfg.performance.progress_update_interval_ms = 500
    cfg.performance.source_timeout_seconds = 5
    cfg.scraper.builtin_enabled = False
    cfg.scraper.source_failure_cache_minutes = 60
    cfg.scraper.fetch_batch_sources = 10
    cfg.scraper.fetch_batch_max_nodes = 1500
    cfg.source_intel.enabled = False
    cfg.data_path = tmp_path
    return cfg


class TestFetchPipeline:
    def test_no_enabled_sources_returns_empty(self, tmp_path):
        """没有 enabled source 时返回空"""
        from freeladder.core.database import Database
        db = Database(str(tmp_path / "test.db"))

        with patch("freeladder.core.config.get_config") as mock_cfg:
            mock_cfg.return_value = _make_mock_config(tmp_path)

            result = run_fetch_pipeline(db)
            assert result["sources_total"] == 0
            assert result["raw_nodes"] == 0

    def test_cancel_token_stops_pipeline(self, tmp_path):
        """cancel_token 停止 pipeline"""
        from freeladder.core.database import Database
        db = Database(str(tmp_path / "test.db"))
        token = CancelToken()
        token.cancel()

        with patch("freeladder.core.config.get_config") as mock_cfg:
            cfg = _make_mock_config(tmp_path)
            cfg.source_intel.enabled = True
            mock_cfg.return_value = cfg

            with patch("freeladder.source_intel.engine.SourceIntelEngine") as MockEngine:
                instance = MagicMock()
                instance.get_enabled_source_urls.return_value = ["https://example.com/sub"]
                MockEngine.return_value = instance

                result = run_fetch_pipeline(db, cancel_token=token, config=cfg)
                assert result["cancelled"] is True

    def test_returns_correct_stats_keys(self, tmp_path):
        """返回的统计包含所有必要字段"""
        from freeladder.core.database import Database
        db = Database(str(tmp_path / "test.db"))

        with patch("freeladder.core.config.get_config") as mock_cfg:
            mock_cfg.return_value = _make_mock_config(tmp_path)

            result = run_fetch_pipeline(db)
            required_keys = {
                "sources_total", "sources_done", "sources_failed",
                "raw_nodes", "submitted_nodes", "inserted", "updated", "cancelled",
                "batch_no", "batch_total", "batch_size",
            }
            assert required_keys.issubset(result.keys())

    def test_all_sources_failed_returns_empty(self, tmp_path):
        """所有源失败缓存时返回空"""
        from freeladder.core.database import Database
        db = Database(str(tmp_path / "test.db"))

        with patch("freeladder.core.config.get_config") as mock_cfg:
            cfg = _make_mock_config(tmp_path)
            cfg.source_intel.enabled = True
            mock_cfg.return_value = cfg

            with patch("freeladder.source_intel.engine.SourceIntelEngine") as MockEngine:
                instance = MagicMock()
                instance.get_enabled_source_urls.return_value = [
                    "https://a.example.com/sub",
                    "https://b.example.com/sub",
                ]
                MockEngine.return_value = instance

                with patch("freeladder.tasks.fetch_pipeline._is_source_failed", return_value=True):
                    result = run_fetch_pipeline(db, config=cfg)
                    assert result["sources_failed"] == 2
                    assert result["raw_nodes"] == 0
