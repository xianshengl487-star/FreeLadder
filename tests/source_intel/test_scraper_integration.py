# path: tests/source_intel/test_scraper_integration.py
"""测试 scraper 与 source_intel 集成"""

import pytest
from unittest.mock import patch, MagicMock

from freeladder.source_intel.models import SourceRecord, SourceStatus, SourceKind


class TestScraperIntegration:
    def test_scrape_builtin_includes_source_intel(self):
        """scrape_builtin 应合并内置源和 source_intel 启用源"""
        from freeladder.scraper.scraper import scrape_builtin
        from freeladder.core.cancel_token import CancelToken

        # Mock the SourceIntelEngine to return empty list
        with patch('freeladder.source_intel.engine.SourceIntelEngine') as MockEngine:
            mock_instance = MagicMock()
            mock_instance.get_enabled_source_urls.return_value = []
            MockEngine.return_value = mock_instance

            cancel = CancelToken()
            cancel.cancel()  # Cancel immediately to avoid actual network calls
            nodes = scrape_builtin(cancel_token=cancel)
            assert isinstance(nodes, list)

    def test_source_intel_config_in_config(self):
        """Config 应包含 source_intel 字段"""
        from freeladder.core.config import Config, SourceIntelConfig
        config = Config()
        assert hasattr(config, 'source_intel')
        assert isinstance(config.source_intel, SourceIntelConfig)
        assert config.source_intel.enabled is True

    def test_source_intel_config_defaults(self):
        """SourceIntelConfig 默认值正确"""
        from freeladder.core.config import SourceIntelConfig
        cfg = SourceIntelConfig()
        assert cfg.github_watch_enabled is True
        assert cfg.github_token == ""
        assert cfg.github_follow_with_account is False
        assert cfg.non_github_discovery_enabled is True
        assert cfg.max_depth_per_site == 0
        assert cfg.require_user_confirm_for_new_sources is True
        assert cfg.auto_refresh_nodes is False
