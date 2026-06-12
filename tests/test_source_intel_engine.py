# path: tests/test_source_intel_engine.py
"""测试 Source Intelligence Engine

验证:
- Engine 可导入
- discover_non_github_sources 不再传空列表
- config 支持 non_github_sites
- get_enabled_source_urls 返回正确 URL
- enable_source / disable_source 正常工作
"""

import pytest
from unittest.mock import patch, MagicMock

from freeladder.source_intel.engine import SourceIntelEngine
from freeladder.source_intel.models import (
    SourceRecord, SourceStatus, SourceKind,
)
from freeladder.source_intel.source_store import SourceStore
from freeladder.source_intel.non_github_discovery import SEED_PUBLIC_PAGES


class TestEngineImport:
    def test_importable(self):
        assert SourceIntelEngine is not None

    def test_class_exists(self):
        assert hasattr(SourceIntelEngine, 'discover_non_github_sources')
        assert hasattr(SourceIntelEngine, 'discover_github_sources')
        assert hasattr(SourceIntelEngine, 'get_enabled_source_urls')
        assert hasattr(SourceIntelEngine, 'enable_source')
        assert hasattr(SourceIntelEngine, 'disable_source')


class TestEngineNonGithubSources:
    def test_non_github_not_empty_list(self, source_store):
        """Engine.discover_non_github_sources 不再传空列表"""
        from freeladder.source_intel.link_extractor import LinkExtractor
        from freeladder.core.config import SourceIntelConfig

        config = SourceIntelConfig(non_github_discovery_enabled=True)
        engine = SourceIntelEngine.__new__(SourceIntelEngine)
        engine._config = config
        engine._store = source_store
        engine._validator = MagicMock()
        engine._extractor = LinkExtractor()
        engine._non_github = MagicMock()
        engine._non_github.get_seed_public_pages.return_value = SEED_PUBLIC_PAGES
        engine._non_github.discover_from_sites.return_value = []

        engine.discover_non_github_sources()

        # Verify discover_from_sites was called with sites, NOT empty list
        call_args = engine._non_github.discover_from_sites.call_args
        sites_passed = call_args[0][0]
        assert sites_passed is not None
        assert isinstance(sites_passed, list)
        # Should NOT be an empty list
        assert len(sites_passed) > 0 or sites_passed is SEED_PUBLIC_PAGES

    def test_non_github_uses_config_sites(self, source_store):
        """Engine 优先使用 config 中的 non_github_sites"""
        from freeladder.source_intel.link_extractor import LinkExtractor
        from freeladder.core.config import SourceIntelConfig

        custom_sites = [{"name": "Custom", "url": "https://custom.com", "enabled": False}]
        config = SourceIntelConfig(
            non_github_discovery_enabled=True,
            non_github_sites=custom_sites,
        )
        engine = SourceIntelEngine.__new__(SourceIntelEngine)
        engine._config = config
        engine._store = source_store
        engine._validator = MagicMock()
        engine._extractor = LinkExtractor()
        engine._non_github = MagicMock()
        engine._non_github.discover_from_sites.return_value = []

        engine.discover_non_github_sources()

        call_args = engine._non_github.discover_from_sites.call_args
        sites_passed = call_args[0][0]
        # Pydantic may copy the list, so compare contents not identity
        assert sites_passed == custom_sites

    def test_non_github_fallback_to_seeds(self, source_store):
        """Engine config 没有 non_github_sites 时 fallback 到种子页面"""
        from freeladder.source_intel.link_extractor import LinkExtractor
        from freeladder.core.config import SourceIntelConfig

        config = SourceIntelConfig(
            non_github_discovery_enabled=True,
            non_github_sites=[],  # Empty config
        )
        engine = SourceIntelEngine.__new__(SourceIntelEngine)
        engine._config = config
        engine._store = source_store
        engine._validator = MagicMock()
        engine._extractor = LinkExtractor()
        engine._non_github = MagicMock()
        engine._non_github.get_seed_public_pages.return_value = SEED_PUBLIC_PAGES
        engine._non_github.discover_from_sites.return_value = []

        engine.discover_non_github_sources()

        engine._non_github.get_seed_public_pages.assert_called_once()
        call_args = engine._non_github.discover_from_sites.call_args
        sites_passed = call_args[0][0]
        assert sites_passed is SEED_PUBLIC_PAGES

    def test_non_github_disabled_returns_empty(self, source_store):
        """non_github_discovery_enabled=False 时返回空"""
        from freeladder.core.config import SourceIntelConfig

        config = SourceIntelConfig(non_github_discovery_enabled=False)
        engine = SourceIntelEngine.__new__(SourceIntelEngine)
        engine._config = config
        engine._store = source_store

        result = engine.discover_non_github_sources()
        assert result == []


class TestEngineGetEnabledUrls:
    def test_no_enabled_sources(self, source_store):
        from freeladder.core.config import SourceIntelConfig
        config = SourceIntelConfig()
        engine = SourceIntelEngine.__new__(SourceIntelEngine)
        engine._config = config
        engine._store = source_store
        urls = engine.get_enabled_source_urls()
        assert urls == []

    def test_enabled_sources_returned(self, source_store):
        from freeladder.core.config import SourceIntelConfig
        config = SourceIntelConfig()
        engine = SourceIntelEngine.__new__(SourceIntelEngine)
        engine._config = config
        engine._store = source_store

        # Add an enabled source directly to store
        s = SourceRecord(
            id="test1", name="Test", url="https://example.com/sub.txt",
            kind=SourceKind.DIRECT, status=SourceStatus.ENABLED, enabled=True,
        )
        source_store.upsert_source(s)

        urls = engine.get_enabled_source_urls()
        assert "https://example.com/sub.txt" in urls


class TestEngineEnableDisable:
    def test_enable_source(self, source_store):
        from freeladder.core.config import SourceIntelConfig
        config = SourceIntelConfig(require_user_confirm_for_new_sources=False)
        engine = SourceIntelEngine.__new__(SourceIntelEngine)
        engine._config = config
        engine._store = source_store

        s = SourceRecord(
            id="test1", name="Test", url="https://example.com/sub.txt",
            kind=SourceKind.DIRECT, status=SourceStatus.CANDIDATE,
        )
        source_store.upsert_source(s)

        result = engine.enable_source("test1", user_confirmed=True)
        assert result is True

    def test_disable_source(self, source_store):
        from freeladder.core.config import SourceIntelConfig
        config = SourceIntelConfig()
        engine = SourceIntelEngine.__new__(SourceIntelEngine)
        engine._config = config
        engine._store = source_store

        s = SourceRecord(
            id="test1", name="Test", url="https://example.com/sub.txt",
            kind=SourceKind.DIRECT, status=SourceStatus.ENABLED, enabled=True,
        )
        source_store.upsert_source(s)

        result = engine.disable_source("test1")
        assert result is True

    def test_enable_nonexistent(self, source_store):
        from freeladder.core.config import SourceIntelConfig
        config = SourceIntelConfig()
        engine = SourceIntelEngine.__new__(SourceIntelEngine)
        engine._config = config
        engine._store = source_store

        result = engine.enable_source("nonexistent")
        assert result is False
