# path: tests/source_intel/test_models.py
"""测试 source_intel 数据模型"""

from freeladder.source_intel.models import (
    SourceRecord, SourceKind, SourceFormat, SourceStatus,
    RepoWatchRecord, DiscoveryResult,
    _make_source_id, _normalize_url,
)


class TestSourceRecord:
    def test_default_values(self):
        s = SourceRecord(url="https://example.com/sub.txt")
        assert s.status == SourceStatus.CANDIDATE
        assert s.enabled is False
        assert s.user_confirmed is False
        assert s.kind == SourceKind.DIRECT
        assert s.format == SourceFormat.AUTO
        assert s.success_count == 0
        assert s.fail_count == 0
        assert s.quality_score == 0.0

    def test_auto_id_generation(self):
        s = SourceRecord(url="https://example.com/sub.txt")
        assert s.id != ""
        assert len(s.id) == 16

    def test_id_stability(self):
        s1 = SourceRecord(url="https://example.com/sub.txt")
        s2 = SourceRecord(url="https://example.com/sub.txt")
        assert s1.id == s2.id

    def test_url_normalization_affects_id(self):
        s1 = SourceRecord(url="https://example.com/sub.txt")
        s2 = SourceRecord(url="https://example.com/sub.txt/")
        assert s1.id == s2.id  # trailing slash normalized

    def test_protocol_stats_empty(self):
        s = SourceRecord(url="https://example.com")
        assert s.protocol_stats == {}

    def test_tags_empty(self):
        s = SourceRecord(url="https://example.com")
        assert s.tags == []


class TestSourceEnum:
    def test_source_kind_values(self):
        assert SourceKind.GITHUB_RAW.value == "github_raw"
        assert SourceKind.RSS.value == "rss"
        assert SourceKind.DIRECT.value == "direct"

    def test_source_format_values(self):
        assert SourceFormat.AUTO.value == "auto"
        assert SourceFormat.CLASH.value == "clash"
        assert SourceFormat.BASE64.value == "base64"

    def test_source_status_values(self):
        assert SourceStatus.CANDIDATE.value == "candidate"
        assert SourceStatus.ENABLED.value == "enabled"
        assert SourceStatus.DEAD.value == "dead"


class TestNormalizeUrl:
    def test_trailing_slash(self):
        assert _normalize_url("https://example.com/") == "https://example.com"

    def test_http_to_https(self):
        assert _normalize_url("http://example.com/sub") == "https://example.com/sub"

    def test_empty_string(self):
        assert _normalize_url("") == ""

    def test_whitespace(self):
        assert _normalize_url("  https://example.com/  ") == "https://example.com"


class TestMakeSourceId:
    def test_consistent(self):
        id1 = _make_source_id("https://example.com/sub.txt")
        id2 = _make_source_id("https://example.com/sub.txt")
        assert id1 == id2

    def test_length(self):
        id1 = _make_source_id("https://example.com/sub.txt")
        assert len(id1) == 16


class TestRepoWatchRecord:
    def test_defaults(self):
        r = RepoWatchRecord(repo="user/repo")
        assert r.enabled is True
        assert r.etag == ""
        assert r.fail_count == 0

    def test_model_dump(self):
        r = RepoWatchRecord(repo="test/repo")
        d = r.model_dump()
        assert d["repo"] == "test/repo"
        assert "etag" in d


class TestDiscoveryResult:
    def test_creation(self):
        source = SourceRecord(url="https://example.com")
        dr = DiscoveryResult(source=source, reason="found in README", confidence=0.8)
        assert dr.reason == "found in README"
        assert dr.confidence == 0.8
