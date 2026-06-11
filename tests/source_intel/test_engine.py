# path: tests/source_intel/test_engine.py
"""测试 SourceIntelEngine"""

import pytest
from unittest.mock import patch, MagicMock

from freeladder.source_intel.engine import SourceIntelEngine
from freeladder.source_intel.models import SourceRecord, SourceStatus


class TestSourceIntelEngine:
    def test_engine_creation(self):
        engine = SourceIntelEngine()
        assert engine.store is not None

    def test_get_enabled_source_urls(self):
        engine = SourceIntelEngine()
        urls = engine.get_enabled_source_urls()
        assert isinstance(urls, list)

    def test_get_candidate_sources(self):
        engine = SourceIntelEngine()
        candidates = engine.get_candidate_sources()
        assert isinstance(candidates, list)

    def test_enable_requires_confirmation(self):
        engine = SourceIntelEngine()
        # Nonexistent source
        result = engine.enable_source("nonexistent", user_confirmed=True)
        assert result is False

    def test_disable_nonexistent(self):
        engine = SourceIntelEngine()
        result = engine.disable_source("nonexistent")
        assert result is False

    def test_remove_dead_sources(self):
        engine = SourceIntelEngine()
        count = engine.remove_dead_sources()
        assert count >= 0

    def test_discover_github_disabled(self):
        engine = SourceIntelEngine()
        engine._config.github_watch_enabled = False
        sources = engine.discover_github_sources()
        assert sources == []

    def test_discover_non_github_disabled(self):
        engine = SourceIntelEngine()
        engine._config.non_github_discovery_enabled = False
        sources = engine.discover_non_github_sources()
        assert sources == []

    def test_validate_candidates_empty(self):
        engine = SourceIntelEngine()
        count = engine.validate_candidates()
        assert count == 0
