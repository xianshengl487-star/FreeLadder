# path: tests/source_intel/test_source_store.py
"""测试 SourceStore 本地 JSON 存储"""

import json
import pytest
from pathlib import Path

from freeladder.source_intel.models import (
    SourceRecord, SourceStatus, RepoWatchRecord,
)
from freeladder.source_intel.source_store import SourceStore


class TestSourceStore:
    def test_empty_store(self, source_store):
        sources = source_store.load_sources()
        assert sources == []

    def test_upsert_and_get(self, source_store, sample_source):
        source_store.upsert_source(sample_source)
        got = source_store.get(sample_source.id)
        assert got is not None
        assert got.url == sample_source.url

    def test_upsert_update(self, source_store, sample_source):
        source_store.upsert_source(sample_source)
        sample_source.name = "updated-name"
        source_store.upsert_source(sample_source)
        got = source_store.get(sample_source.id)
        assert got.name == "updated-name"

    def test_list_enabled(self, source_store, enabled_source):
        source_store.upsert_source(enabled_source)
        enabled = source_store.list_enabled()
        assert len(enabled) == 1
        assert enabled[0].status == SourceStatus.ENABLED

    def test_list_candidates(self, source_store, sample_source):
        source_store.upsert_source(sample_source)
        candidates = source_store.list_candidates()
        assert len(candidates) == 1

    def test_enable_disable(self, source_store, sample_source):
        source_store.upsert_source(sample_source)
        assert source_store.enable(sample_source.id) is True
        got = source_store.get(sample_source.id)
        assert got.status == SourceStatus.ENABLED

        assert source_store.disable(sample_source.id) is True
        got = source_store.get(sample_source.id)
        assert got.status == SourceStatus.DISABLED

    def test_enable_nonexistent(self, source_store):
        assert source_store.enable("nonexistent") is False

    def test_disable_nonexistent(self, source_store):
        assert source_store.disable("nonexistent") is False

    def test_mark_success(self, source_store, sample_source):
        source_store.upsert_source(sample_source)
        source_store.mark_success(sample_source.id, 50, {"vmess": 30, "vless": 20})
        got = source_store.get(sample_source.id)
        assert got.success_count == 1
        assert got.last_node_count == 50
        assert got.protocol_stats == {"vmess": 30, "vless": 20}

    def test_mark_failed(self, source_store, sample_source):
        source_store.upsert_source(sample_source)
        source_store.mark_failed(sample_source.id, "timeout")
        got = source_store.get(sample_source.id)
        assert got.fail_count == 1
        assert got.last_error == "timeout"
        assert got.status == SourceStatus.FAILED

    def test_mark_dead(self, source_store, sample_source):
        source_store.upsert_source(sample_source)
        sample_source.fail_count = 5
        source_store.upsert_source(sample_source)
        source_store.mark_dead_if_needed(sample_source.id, max_failures=5)
        got = source_store.get(sample_source.id)
        assert got.status == SourceStatus.DEAD

    def test_json_corruption_backup(self, source_store, tmp_data_dir):
        """JSON 损坏时自动备份"""
        corrupt_file = tmp_data_dir / "source_intel.json"
        corrupt_file.write_text("{invalid json", encoding="utf-8")

        sources = source_store.load_sources()
        assert sources == []

        # 检查备份文件创建
        backup = tmp_data_dir / "source_intel.json.bak"
        assert backup.exists()

    def test_atomic_save(self, source_store, sample_source, tmp_data_dir):
        """原子保存不产生临时文件"""
        source_store.upsert_source(sample_source)
        tmp_files = list(tmp_data_dir.glob("*.tmp"))
        assert len(tmp_files) == 0

    def test_remove_source(self, source_store, sample_source):
        source_store.upsert_source(sample_source)
        assert source_store.remove_source(sample_source.id) is True
        got = source_store.get(sample_source.id)
        assert got is None

    def test_remove_nonexistent(self, source_store):
        assert source_store.remove_source("nonexistent") is False

    def test_repo_watch(self, source_store):
        record = RepoWatchRecord(repo="test/repo")
        source_store.upsert_repo_watch(record)
        records = source_store.load_repo_watch()
        assert len(records) == 1
        assert records[0].repo == "test/repo"

    def test_repo_watch_update(self, source_store):
        record = RepoWatchRecord(repo="test/repo", etag="v1")
        source_store.upsert_repo_watch(record)
        record.etag = "v2"
        source_store.upsert_repo_watch(record)
        records = source_store.load_repo_watch()
        assert len(records) == 1
        assert records[0].etag == "v2"
