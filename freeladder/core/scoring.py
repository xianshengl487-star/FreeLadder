# path: freeladder/core/scoring.py
"""评分算法模块

评分模型 (0-100):
  可用性 40% + 延迟 30% + 稳定性 20% + 新鲜度 10%
"""

import time
from datetime import datetime, timedelta
from typing import Optional

from .models import Node


def _availability_score(node: Node) -> float:
    """可用性评分 (0-40)"""
    if not node.alive:
        # 未通过测试：根据连续失败次数递减
        if node.fail_count == 0:
            return 20.0  # 未测试过
        elif node.fail_count <= 3:
            return 10.0
        elif node.fail_count <= 7:
            return 5.0
        else:
            return 0.0

    # 通过测试：基于成功率
    total = node.success_count + node.fail_count
    if total == 0:
        return 30.0
    success_rate = node.success_count / total
    return success_rate * 40.0


def _latency_score(node: Node) -> float:
    """延迟评分 (0-30)"""
    if not node.alive or node.latency is None:
        return 0.0

    lat = node.latency
    if lat < 200:
        return 30.0
    elif lat < 300:
        return 28.0
    elif lat < 500:
        return 24.0
    elif lat < 800:
        return 18.0
    elif lat < 1200:
        return 12.0
    elif lat < 2000:
        return 6.0
    else:
        return 2.0


def _stability_score(node: Node) -> float:
    """稳定性评分 (0-20)"""
    total = node.success_count + node.fail_count
    if total == 0:
        return 10.0  # 未测试过，给中等分

    success_rate = node.success_count / total

    # 成功率
    if success_rate >= 0.95:
        base = 20.0
    elif success_rate >= 0.85:
        base = 16.0
    elif success_rate >= 0.70:
        base = 12.0
    elif success_rate >= 0.50:
        base = 8.0
    else:
        base = 3.0

    # 连续失败惩罚
    if node.fail_count >= 5:
        base *= 0.5
    elif node.fail_count >= 3:
        base *= 0.7

    return base


def _freshness_score(node: Node) -> float:
    """新鲜度评分 (0-10)"""
    if not node.last_checked:
        return 3.0  # 从未测试

    try:
        last_check = datetime.strptime(node.last_checked, "%Y-%m-%d %H:%M:%S")
    except (ValueError, TypeError):
        return 3.0

    now = datetime.now()
    diff = now - last_check

    if diff < timedelta(minutes=10):
        return 10.0
    elif diff < timedelta(minutes=30):
        return 8.0
    elif diff < timedelta(hours=1):
        return 6.0
    elif diff < timedelta(hours=3):
        return 4.0
    elif diff < timedelta(hours=12):
        return 2.0
    else:
        return 1.0


def calculate_score(node: Node) -> float:
    """计算综合评分 (0-100)"""
    score = (
        _availability_score(node) +
        _latency_score(node) +
        _stability_score(node) +
        _freshness_score(node)
    )
    return round(max(0.0, min(100.0, score)), 1)


def get_signal(score: float) -> str:
    """根据分数返回信号等级"""
    if score >= 90:
        return "★★★★★"
    elif score >= 75:
        return "★★★★"
    elif score >= 60:
        return "★★★"
    elif score >= 40:
        return "★★"
    else:
        return "★"
