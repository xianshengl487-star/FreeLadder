# path: freeladder/source_intel/source_health.py
"""源健康度评分

根据源的稳定性、节点数量、协议丰富度、最近成功时间、失败次数、更新频率计算健康度。

评分公式:
quality_score =
    0.35 * success_rate
  + 0.20 * freshness_score
  + 0.20 * node_count_score
  + 0.15 * protocol_diversity_score
  + 0.10 * stability_score
  - failure_penalty
"""

import time
from datetime import datetime, timedelta

from loguru import logger

from .models import SourceRecord, SourceStatus


class SourceHealth:
    """源健康度评分系统"""

    def __init__(self, stale_days: int = 7, remove_dead_after: int = 5):
        self._stale_days = stale_days
        self._remove_dead_after = remove_dead_after

    def compute_score(self, source: SourceRecord) -> float:
        """计算源健康度分数 (0-100)"""
        # 成功率
        total = source.success_count + source.fail_count
        if total == 0:
            success_rate = 0.5  # 新源给中等分
        else:
            success_rate = source.success_count / total

        # 新鲜度
        freshness_score = self._freshness_score(source.last_success)

        # 节点数量评分
        node_count_score = self._node_count_score(source.last_node_count)

        # 协议多样性
        protocol_diversity = self._protocol_diversity_score(source.protocol_stats)

        # 稳定性
        stability_score = self._stability_score(source)

        # 失败惩罚
        failure_penalty = self._failure_penalty(source)

        score = (
            0.35 * success_rate * 100
            + 0.20 * freshness_score * 100
            + 0.20 * node_count_score * 100
            + 0.15 * protocol_diversity * 100
            + 0.10 * stability_score * 100
            - failure_penalty
        )

        return max(0.0, min(100.0, round(score, 1)))

    def rank_sources(self, sources: list[SourceRecord]) -> list[SourceRecord]:
        """按健康度排序"""
        for s in sources:
            s.quality_score = self.compute_score(s)
        return sorted(sources, key=lambda s: s.quality_score, reverse=True)

    def update_after_success(
        self, source: SourceRecord, node_count: int, protocol_stats: dict
    ) -> SourceRecord:
        """成功后更新健康度"""
        now = time.strftime("%Y-%m-%d %H:%M:%S")
        source.success_count += 1
        source.fail_count = 0
        source.last_success = now
        source.last_checked = now
        source.last_node_count = node_count
        source.protocol_stats = protocol_stats
        source.last_error = ""
        # 更新平均节点数（指数移动平均）
        if source.avg_node_count == 0:
            source.avg_node_count = float(node_count)
        else:
            source.avg_node_count = source.avg_node_count * 0.7 + node_count * 0.3
        source.quality_score = self.compute_score(source)
        # 如果之前是 FAILED/STALE，恢复为 CANDIDATE
        if source.status in (SourceStatus.FAILED, SourceStatus.STALE):
            source.status = SourceStatus.CANDIDATE
        return source

    def update_after_failure(
        self, source: SourceRecord, error: str
    ) -> SourceRecord:
        """失败后更新健康度"""
        now = time.strftime("%Y-%m-%d %H:%M:%S")
        source.fail_count += 1
        source.last_failed = now
        source.last_checked = now
        source.last_error = error[:200]
        source.status = SourceStatus.FAILED
        # 连续失败超阈值标记 DEAD
        if source.fail_count >= self._remove_dead_after:
            source.status = SourceStatus.DEAD
            source.enabled = False
            logger.warning(f"源已标记 DEAD: {source.name} (连续失败 {source.fail_count} 次)")
        # 超过 stale 天数未成功
        if source.last_success:
            try:
                last = datetime.fromisoformat(source.last_success)
                if datetime.now() - last > timedelta(days=self._stale_days):
                    source.status = SourceStatus.STALE
            except (ValueError, TypeError):
                pass
        source.quality_score = self.compute_score(source)
        return source

    def _freshness_score(self, last_success: str) -> float:
        """新鲜度评分: 0-1, 越近越好"""
        if not last_success:
            return 0.0
        try:
            last = datetime.fromisoformat(last_success)
            hours_ago = (datetime.now() - last).total_seconds() / 3600
            # 24小时内满分，7天后归零
            if hours_ago <= 24:
                return 1.0
            elif hours_ago <= 168:
                return 1.0 - (hours_ago - 24) / 144
            else:
                return 0.0
        except (ValueError, TypeError):
            return 0.0

    def _node_count_score(self, node_count: int) -> float:
        """节点数量评分: 0-1"""
        if node_count <= 0:
            return 0.0
        if node_count >= 50:
            return 1.0
        if node_count >= 20:
            return 0.8
        if node_count >= 5:
            return 0.5
        return 0.2

    def _protocol_diversity_score(self, protocol_stats: dict) -> float:
        """协议多样性评分: 0-1"""
        if not protocol_stats:
            return 0.0
        unique = len(protocol_stats)
        if unique >= 4:
            return 1.0
        if unique >= 3:
            return 0.8
        if unique >= 2:
            return 0.5
        return 0.3

    def _stability_score(self, source: SourceRecord) -> float:
        """稳定性评分: 0-1"""
        total = source.success_count + source.fail_count
        if total == 0:
            return 0.5
        # 连续成功次数越多越好
        if source.fail_count == 0:
            return 1.0
        if source.fail_count <= 1:
            return 0.8
        if source.fail_count <= 2:
            return 0.5
        return 0.2

    def _failure_penalty(self, source: SourceRecord) -> float:
        """失败惩罚: 连续失败越多惩罚越大"""
        if source.fail_count <= 1:
            return 0.0
        return min(source.fail_count * 3.0, 20.0)
