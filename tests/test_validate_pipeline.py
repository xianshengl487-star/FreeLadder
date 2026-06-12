# path: tests/test_validate_pipeline.py
"""测试 ValidatePipeline

覆盖:
- ValidatePipeline 只验证候选源
- ValidatePipeline 支持 cancel_token
- ValidatePipeline 返回正确统计
"""

import pytest
from unittest.mock import patch, MagicMock

from freeladder.core.cancel_token import CancelToken
from freeladder.source_intel.models import SourceRecord, SourceStatus, SourceKind
from freeladder.tasks.validate_pipeline import run_validate_pipeline


class TestValidatePipeline:
    def test_no_candidates_returns_empty(self, tmp_path):
        """没有候选源时返回空"""
        from freeladder.source_intel.source_store import SourceStore
        store = SourceStore(data_dir=tmp_path)
        validator = MagicMock()
        health = MagicMock()

        result = run_validate_pipeline(store, validator, health)
        assert result["total"] == 0
        assert result["validated"] == 0

    def test_cancel_token_stops(self, tmp_path):
        """cancel_token 停止验证"""
        from freeladder.source_intel.source_store import SourceStore
        store = SourceStore(data_dir=tmp_path)
        token = CancelToken()
        token.cancel()

        # Need at least one candidate for cancel to trigger
        s = SourceRecord(
            id="test1", name="Test", url="https://example.com/sub.txt",
            kind=SourceKind.DIRECT, status=SourceStatus.CANDIDATE,
        )
        store.upsert_source(s)

        validator = MagicMock()
        health = MagicMock()

        with patch("freeladder.core.config.get_config") as mock_cfg:
            cfg = MagicMock()
            cfg.performance.validate_workers = 2
            cfg.performance.progress_update_interval_ms = 500
            mock_cfg.return_value = cfg

            result = run_validate_pipeline(store, validator, health, cancel_token=token)
            assert result["cancelled"] is True

    def test_validates_candidates(self, tmp_path):
        """验证候选源"""
        from freeladder.source_intel.source_store import SourceStore
        store = SourceStore(data_dir=tmp_path)

        s = SourceRecord(
            id="test1", name="Test", url="https://example.com/sub.txt",
            kind=SourceKind.DIRECT, status=SourceStatus.CANDIDATE,
        )
        store.upsert_source(s)

        validator = MagicMock()
        validator.validate.return_value = {"valid": True, "node_count": 5, "protocol_stats": {"vmess": 5}}
        health = MagicMock()
        health.update_after_success.return_value = s

        with patch("freeladder.core.config.get_config") as mock_cfg:
            cfg = MagicMock()
            cfg.performance.validate_workers = 2
            cfg.performance.progress_update_interval_ms = 500
            mock_cfg.return_value = cfg

            result = run_validate_pipeline(store, validator, health)
            assert result["total"] >= 1
            assert result["validated"] >= 1

    def test_returns_correct_keys(self, tmp_path):
        """返回的统计包含必要字段"""
        from freeladder.source_intel.source_store import SourceStore
        store = SourceStore(data_dir=tmp_path)
        validator = MagicMock()
        health = MagicMock()

        result = run_validate_pipeline(store, validator, health)
        assert "total" in result
        assert "validated" in result
        assert "failed" in result
        assert "cancelled" in result
