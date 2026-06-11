# path: tests/source_intel/test_source_health.py
"""测试 SourceHealth 源健康度评分"""

from freeladder.source_intel.models import SourceRecord, SourceStatus
from freeladder.source_intel.source_health import SourceHealth


class TestSourceHealth:
    def test_new_source_score(self, source_health):
        s = SourceRecord(url="https://example.com/sub.txt")
        score = source_health.compute_score(s)
        assert 0 <= score <= 100

    def test_high_success_rate(self, source_health):
        s = SourceRecord(
            url="https://example.com/sub.txt",
            success_count=10,
            fail_count=1,
            last_success="2026-06-12 10:00:00",
            last_node_count=50,
            protocol_stats={"vmess": 30, "vless": 20},
        )
        score = source_health.compute_score(s)
        assert score > 60

    def test_low_success_rate(self, source_health):
        s = SourceRecord(
            url="https://example.com/sub.txt",
            success_count=1,
            fail_count=10,
            last_node_count=5,
        )
        score = source_health.compute_score(s)
        assert score < 40

    def test_rank_sources(self, source_health):
        good = SourceRecord(
            url="https://example.com/good.txt",
            success_count=10,
            fail_count=0,
            last_success="2026-06-12 10:00:00",
            last_node_count=50,
        )
        bad = SourceRecord(
            url="https://example.com/bad.txt",
            success_count=1,
            fail_count=10,
            last_node_count=5,
        )
        ranked = source_health.rank_sources([bad, good])
        assert ranked[0].url == good.url

    def test_update_after_success(self, source_health):
        s = SourceRecord(url="https://example.com/sub.txt")
        s = source_health.update_after_success(s, 30, {"vmess": 20})
        assert s.success_count == 1
        assert s.last_node_count == 30
        assert s.protocol_stats == {"vmess": 20}
        assert s.avg_node_count == 30.0

    def test_update_after_failure(self, source_health):
        s = SourceRecord(url="https://example.com/sub.txt")
        s = source_health.update_after_failure(s, "timeout")
        assert s.fail_count == 1
        assert s.last_error == "timeout"
        assert s.status == SourceStatus.FAILED

    def test_dead_after_failures(self, source_health):
        s = SourceRecord(url="https://example.com/sub.txt", fail_count=4)
        s = source_health.update_after_failure(s, "error")
        assert s.status == SourceStatus.DEAD
        assert s.fail_count == 5

    def test_score_range(self, source_health):
        s = SourceRecord(
            url="https://example.com/sub.txt",
            success_count=100,
            fail_count=0,
            last_success="2026-06-12 10:00:00",
            last_node_count=100,
            protocol_stats={"vmess": 30, "vless": 30, "trojan": 20, "ss": 20},
        )
        score = source_health.compute_score(s)
        assert 0 <= score <= 100

    def test_empty_protocol_stats(self, source_health):
        s = SourceRecord(url="https://example.com/sub.txt")
        score = source_health.compute_score(s)
        assert score >= 0

    def test_freshness_score(self, source_health):
        # 最近成功 -> 高分
        s_recent = SourceRecord(
            url="https://example.com/recent.txt",
            success_count=5,
            fail_count=0,
            last_success="2026-06-12 10:00:00",
            last_node_count=50,
        )
        # 很久前成功 -> 低分
        s_old = SourceRecord(
            url="https://example.com/old.txt",
            success_count=5,
            fail_count=0,
            last_success="2026-05-01 10:00:00",
            last_node_count=50,
        )
        score_recent = source_health.compute_score(s_recent)
        score_old = source_health.compute_score(s_old)
        assert score_recent > score_old
