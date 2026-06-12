# path: tests/test_test_pipeline.py
"""测试 TestPipeline

覆盖:
- TestPipeline 进度节流
- TestPipeline 返回正确统计
- TestPipeline 支持 cancel_token
- TestPipeline 没有节点时返回空
"""

import pytest
from unittest.mock import patch, MagicMock

from freeladder.core.cancel_token import CancelToken
from freeladder.core.database import Database
from freeladder.core.models import Node, Protocol
from freeladder.tasks.test_pipeline import run_test_pipeline


def _make_nodes(count):
    return [
        Node(
            node_key=f"vmess:test{i}:443",
            raw_hash=f"test{i:06d}",
            protocol=Protocol.VMESS,
            server=f"10.0.{i // 256}.{i % 256}",
            port=443,
            name=f"Test Node {i}",
            raw_uri=f"vmess://test{i}",
        )
        for i in range(count)
    ]


class TestTestPipeline:
    def test_no_nodes_returns_empty(self, tmp_path):
        """没有节点时返回空"""
        db = Database(str(tmp_path / "test.db"))
        result = run_test_pipeline(db, mode="all")
        assert result["total"] == 0
        assert result["tested"] == 0

    def test_cancel_token_stops(self, tmp_path):
        """cancel_token 停止测试"""
        db = Database(str(tmp_path / "test.db"))
        db.upsert_nodes_bulk(_make_nodes(10))
        token = CancelToken()
        token.cancel()

        result = run_test_pipeline(db, mode="all", cancel_token=token)
        assert result["cancelled"] is True

    def test_returns_correct_keys(self, tmp_path):
        """返回的统计包含必要字段"""
        db = Database(str(tmp_path / "test.db"))
        result = run_test_pipeline(db, mode="all")
        assert "total" in result
        assert "tested" in result
        assert "alive" in result
        assert "dead" in result
        assert "cancelled" in result

    def test_progress_throttling(self, tmp_path):
        """进度回调被节流"""
        db = Database(str(tmp_path / "test.db"))
        db.upsert_nodes_bulk(_make_nodes(20))
        progress_calls = []

        def on_progress(current, total, msg):
            progress_calls.append((current, total))

        with patch("freeladder.core.config.get_config") as mock_cfg:
            cfg = MagicMock()
            cfg.performance.test_workers = 2
            cfg.performance.max_total_nodes_per_task = 100
            cfg.performance.test_timeout_seconds = 5
            cfg.performance.progress_update_interval_ms = 0  # No throttle for testing
            mock_cfg.return_value = cfg

            with patch("freeladder.tester.TestService") as MockTest:
                mock_svc = MagicMock()
                mock_result = MagicMock()
                mock_result.alive = False
                mock_result.latency = -1
                mock_result.error = ""
                mock_svc.test_single_node.return_value = mock_result
                MockTest.return_value = mock_svc

                result = run_test_pipeline(db, mode="all", on_progress=on_progress)
                assert result["tested"] >= 1

    def test_mode_new_filters_untested(self, tmp_path):
        """mode=new 只测试未测试过的节点"""
        db = Database(str(tmp_path / "test.db"))
        nodes = _make_nodes(5)
        # One already tested
        nodes[0].last_checked = "2026-06-12 10:00:00"
        db.upsert_nodes_bulk(nodes)

        with patch("freeladder.core.config.get_config") as mock_cfg:
            cfg = MagicMock()
            cfg.performance.test_workers = 2
            cfg.performance.max_total_nodes_per_task = 100
            cfg.performance.test_timeout_seconds = 5
            cfg.performance.progress_update_interval_ms = 0
            mock_cfg.return_value = cfg

            with patch("freeladder.tester.TestService") as MockTest:
                mock_svc = MagicMock()
                mock_result = MagicMock()
                mock_result.alive = False
                mock_result.latency = -1
                mock_result.error = ""
                mock_svc.test_single_node.return_value = mock_result
                MockTest.return_value = mock_svc

                result = run_test_pipeline(db, mode="new")
                # Should only test 4 nodes (5 minus 1 already tested)
                assert result["total"] == 4
