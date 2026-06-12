# path: tests/test_performance_config.py
"""测试 PerformanceConfig

覆盖:
- PerformanceConfig 默认值
- PerformanceConfig 加载
- Config 中 performance 字段存在
"""

import pytest
from freeladder.core.config import PerformanceConfig, Config


class TestPerformanceConfig:
    def test_default_values(self):
        cfg = PerformanceConfig()
        assert cfg.enabled is True
        assert cfg.fetch_workers == 8
        assert cfg.validate_workers == 8
        assert cfg.test_workers == 32
        assert cfg.mihomo_test_workers == 4
        assert cfg.db_batch_size == 500
        assert cfg.db_queue_max_size == 3000
        assert cfg.max_pending_futures == 200
        assert cfg.max_total_nodes_per_task == 20000
        assert cfg.max_nodes_per_source == 1000
        assert cfg.progress_update_interval_ms == 500
        assert cfg.log_update_interval_ms == 500
        assert cfg.task_timeout_seconds == 1800
        assert cfg.source_timeout_seconds == 15
        assert cfg.test_timeout_seconds == 8
        assert cfg.enable_db_wal is True

    def test_config_has_performance(self):
        cfg = Config()
        assert cfg.performance is not None
        assert isinstance(cfg.performance, PerformanceConfig)

    def test_custom_values(self):
        cfg = PerformanceConfig(fetch_workers=4, test_workers=16)
        assert cfg.fetch_workers == 4
        assert cfg.test_workers == 16

    def test_config_from_dict(self):
        data = {
            "performance": {
                "fetch_workers": 2,
                "enable_db_wal": False,
            }
        }
        cfg = Config(**data)
        assert cfg.performance.fetch_workers == 2
        assert cfg.performance.enable_db_wal is False
        # Other defaults should be preserved
        assert cfg.performance.test_workers == 32
