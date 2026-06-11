# path: tests/source_intel/conftest.py
"""Source Intelligence Engine 测试共享 fixtures"""

import pytest
import tempfile
from pathlib import Path

from freeladder.source_intel.models import (
    SourceRecord, SourceKind, SourceFormat, SourceStatus,
    RepoWatchRecord, DiscoveryResult,
)
from freeladder.source_intel.source_store import SourceStore
from freeladder.source_intel.link_extractor import LinkExtractor
from freeladder.source_intel.source_health import SourceHealth
from freeladder.source_intel.source_validator import SourceValidator


@pytest.fixture
def tmp_data_dir():
    """创建临时数据目录"""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def source_store(tmp_data_dir):
    """创建临时 SourceStore"""
    return SourceStore(data_dir=tmp_data_dir)


@pytest.fixture
def link_extractor():
    """创建 LinkExtractor"""
    return LinkExtractor()


@pytest.fixture
def source_health():
    """创建 SourceHealth"""
    return SourceHealth(stale_days=7, remove_dead_after=5)


@pytest.fixture
def sample_source():
    """创建示例 SourceRecord"""
    return SourceRecord(
        id="test123",
        name="test-source",
        url="https://example.com/sub.txt",
        kind=SourceKind.DIRECT,
        format=SourceFormat.TEXT,
        status=SourceStatus.CANDIDATE,
    )


@pytest.fixture
def enabled_source():
    """创建已启用的 SourceRecord"""
    return SourceRecord(
        id="enabled1",
        name="enabled-source",
        url="https://example.com/enabled.yml",
        kind=SourceKind.GITHUB_RAW,
        format=SourceFormat.CLASH,
        status=SourceStatus.ENABLED,
        enabled=True,
        user_confirmed=True,
        success_count=10,
        fail_count=1,
        last_node_count=50,
        avg_node_count=45.0,
        protocol_stats={"vmess": 30, "vless": 20},
        last_success="2026-06-12 10:00:00",
    )


@pytest.fixture
def dead_source():
    """创建 DEAD 源"""
    return SourceRecord(
        id="dead1",
        name="dead-source",
        url="https://example.com/dead.txt",
        status=SourceStatus.DEAD,
        fail_count=10,
        last_error="连续失败",
    )
