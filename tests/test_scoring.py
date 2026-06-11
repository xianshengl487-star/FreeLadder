# path: tests/test_scoring.py
"""测试评分算法模块"""

import pytest
from freeladder.core.scoring import (
    calculate_score,
    get_signal,
    _availability_score,
    _latency_score,
    _stability_score,
    _freshness_score,
)
from tests.conftest import make_node
from freeladder.core.models import Protocol


class TestAvailabilityScore:
    """可用性评分 (0-40)"""

    def test_untested_node(self):
        node = make_node(fail_count=0, alive=False)
        assert _availability_score(node) == 20.0

    def test_alive_no_history(self):
        node = make_node(alive=True, success_count=0, fail_count=0)
        assert _availability_score(node) == 30.0

    def test_alive_perfect_success(self):
        node = make_node(alive=True, success_count=10, fail_count=0)
        assert _availability_score(node) == 40.0

    def test_alive_50_percent_success(self):
        node = make_node(alive=True, success_count=5, fail_count=5)
        assert _availability_score(node) == pytest.approx(20.0, abs=0.1)

    def test_alive_90_percent_success(self):
        node = make_node(alive=True, success_count=9, fail_count=1)
        assert _availability_score(node) == pytest.approx(36.0, abs=0.1)

    @pytest.mark.parametrize("fail_count,expected", [
        (1, 10.0),
        (2, 10.0),
        (3, 10.0),
        (4, 5.0),
        (5, 5.0),
        (7, 5.0),
        (8, 0.0),
        (15, 0.0),
    ])
    def test_dead_by_fail_count(self, fail_count, expected):
        node = make_node(alive=False, fail_count=fail_count)
        assert _availability_score(node) == expected


class TestLatencyScore:
    """延迟评分 (0-30)"""

    def test_dead_node(self):
        node = make_node(alive=False)
        assert _latency_score(node) == 0.0

    def test_alive_no_latency(self):
        node = make_node(alive=True, latency=None)
        assert _latency_score(node) == 0.0

    @pytest.mark.parametrize("latency,expected", [
        (50, 30.0),
        (100, 30.0),
        (199, 30.0),
        (200, 28.0),
        (299, 28.0),
        (300, 24.0),
        (499, 24.0),
        (500, 18.0),
        (799, 18.0),
        (800, 12.0),
        (1199, 12.0),
        (1200, 6.0),
        (1999, 6.0),
        (2000, 2.0),
        (5000, 2.0),
    ])
    def test_latency_tiers(self, latency, expected):
        node = make_node(alive=True, latency=latency)
        assert _latency_score(node) == expected


class TestStabilityScore:
    """稳定性评分 (0-20)"""

    def test_untested_node(self):
        node = make_node(success_count=0, fail_count=0)
        assert _stability_score(node) == 10.0

    def test_perfect_success_rate(self):
        node = make_node(success_count=20, fail_count=0)
        assert _stability_score(node) == 20.0

    def test_95_percent_success(self):
        node = make_node(success_count=19, fail_count=1)
        assert _stability_score(node) == 20.0

    def test_85_percent_success(self):
        # 85% success rate = base 16.0, but fail_count=15 >= 5 triggers 0.5 penalty
        node = make_node(success_count=85, fail_count=15)
        assert _stability_score(node) == pytest.approx(8.0, abs=0.1)

    def test_85_percent_success_low_failures(self):
        # 85% success rate = base 16.0, fail_count=1 < 3 so no penalty
        node = make_node(success_count=17, fail_count=3)
        assert _stability_score(node) == pytest.approx(11.2, abs=0.1)

    def test_70_percent_success(self):
        # 70% success rate = base 12.0, fail_count=3 triggers 0.7 penalty
        node = make_node(success_count=7, fail_count=3)
        assert _stability_score(node) == pytest.approx(8.4, abs=0.1)

    def test_50_percent_success(self):
        # 50% success rate = base 8.0, fail_count=5 triggers 0.5 penalty
        node = make_node(success_count=5, fail_count=5)
        assert _stability_score(node) == pytest.approx(4.0, abs=0.1)

    def test_low_success_rate(self):
        # <50% success = base 3.0, fail_count=9 >= 5 triggers 0.5 penalty
        node = make_node(success_count=1, fail_count=9)
        assert _stability_score(node) == pytest.approx(1.5, abs=0.1)

    def test_consecutive_fail_5_penalized(self):
        # 60% success = base 8.0 * 0.5 (fail_count=6 >= 5) = 4.0
        node = make_node(success_count=9, fail_count=6)
        assert _stability_score(node) == pytest.approx(4.0, abs=0.1)

    def test_consecutive_fail_3_penalized(self):
        # 77% success = base 12.0 * 0.7 (fail_count=3 >= 3) = 8.4
        node = make_node(success_count=10, fail_count=3)
        assert _stability_score(node) == pytest.approx(8.4, abs=0.1)


class TestFreshnessScore:
    """新鲜度评分 (0-10)"""

    def test_never_checked(self):
        node = make_node(last_checked="")
        assert _freshness_score(node) == 3.0

    def test_invalid_date_format(self):
        node = make_node(last_checked="not-a-date")
        assert _freshness_score(node) == 3.0


class TestCalculateScore:
    """综合评分"""

    def test_perfect_score(self):
        node = make_node(
            alive=True, latency=50,
            success_count=100, fail_count=0,
            last_checked="2026-06-12 12:00:00",
        )
        score = calculate_score(node)
        assert score >= 90.0

    def test_zero_score(self):
        # availability=0 (fail_count>7) + latency=0 (dead) + stability=1.5 (0% success * 0.5 penalty) + freshness=1.0 (old date) = 2.5
        node = make_node(
            alive=False, latency=None,
            success_count=0, fail_count=100,
            last_checked="2020-01-01 00:00:00",
        )
        score = calculate_score(node)
        assert score == pytest.approx(2.5, abs=0.1)

    def test_score_is_capped_at_100(self):
        node = make_node(
            alive=True, latency=1,
            success_count=1000, fail_count=0,
            last_checked="2026-06-12 12:00:00",
        )
        score = calculate_score(node)
        assert score <= 100.0

    def test_score_is_not_negative(self):
        node = make_node(
            alive=False, latency=None,
            success_count=0, fail_count=100,
            last_checked="2020-01-01 00:00:00",
        )
        score = calculate_score(node)
        assert score >= 0.0


class TestGetSignal:
    """信号等级"""

    @pytest.mark.parametrize("score,expected", [
        (100, "★★★★★"),
        (90, "★★★★★"),
        (89.9, "★★★★"),
        (75, "★★★★"),
        (74.9, "★★★"),
        (60, "★★★"),
        (59.9, "★★"),
        (40, "★★"),
        (39.9, "★"),
        (0, "★"),
    ])
    def test_signal_tiers(self, score, expected):
        assert get_signal(score) == expected
