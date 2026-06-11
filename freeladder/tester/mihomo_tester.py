# path: freeladder/tester/mihomo_tester.py
"""Mihomo 真实延迟测试模块

通过 Mihomo External Controller API 对高级协议节点进行真实延迟测试。
支持 VMess、VLESS、Trojan、Hysteria、TUIC、SS 等协议。
"""

import math
from typing import Callable, Optional

from loguru import logger

from freeladder.core.config import get_config
from freeladder.core.models import Node, TestResult, ADVANCED_PROTOCOLS
from .mihomo_manager import MihomoManager

# 每批测试的节点数量上限
BATCH_SIZE = 50


def _nodes_to_proxies(nodes: list[Node]) -> list[dict]:
    """将 Node 列表转换为 Mihomo proxy 字典列表

    只处理有 clash_proxy 的节点。
    """
    proxies = []
    for node in nodes:
        if node.clash_proxy:
            proxies.append(node.clash_proxy)
        else:
            logger.debug(f"跳过无 clash_proxy 的节点: {node.node_key}")
    return proxies


def mihomo_test_nodes(
    nodes: list[Node],
    on_progress: Optional[Callable[[int, int, str], None]] = None,
) -> list[TestResult]:
    """使用 Mihomo 测试高级协议节点

    流程:
    1. 过滤出高级协议节点
    2. 转换为 Mihomo proxy 格式
    3. 分批启动 Mihomo 进行测试
    4. 收集测试结果

    Args:
        nodes: 待测试节点列表
        on_progress: 进度回调 (current, total, message)

    Returns:
        TestResult 列表
    """
    config = get_config()
    manager = MihomoManager()

    if not manager.is_available:
        logger.warning("Mihomo 不可用，跳过高级协议测试")
        return [TestResult(
            node_id=n.id,
            node_key=n.node_key,
            alive=False,
            error="Mihomo 不可用",
            test_mode="mihomo_missing",
        ) for n in nodes]

    # 过滤高级协议节点
    advanced_nodes = [n for n in nodes if n.protocol in ADVANCED_PROTOCOLS]
    if not advanced_nodes:
        logger.info("没有需要 Mihomo 测试的高级协议节点")
        return []

    logger.info(f"准备使用 Mihomo 测试 {len(advanced_nodes)} 个高级协议节点")

    all_results: list[TestResult] = []
    total = len(advanced_nodes)

    # 分批测试
    for batch_start in range(0, total, BATCH_SIZE):
        batch = advanced_nodes[batch_start:batch_start + BATCH_SIZE]
        batch_num = batch_start // BATCH_SIZE + 1
        total_batches = math.ceil(total / BATCH_SIZE)

        if on_progress:
            on_progress(
                batch_start,
                total,
                f"Mihomo 批次 {batch_num}/{total_batches}，{len(batch)} 个节点"
            )

        logger.info(f"Mihomo 批次 {batch_num}/{total_batches}: {len(batch)} 个节点")

        batch_results = _test_batch(manager, batch, config, on_progress, batch_start, total)
        all_results.extend(batch_results)

    logger.info(f"Mihomo 测试完成: {len(all_results)} 个结果")
    return all_results


def _test_batch(
    manager: MihomoManager,
    nodes: list[Node],
    config,
    on_progress: Optional[Callable],
    batch_offset: int,
    total: int,
) -> list[TestResult]:
    """测试一批节点"""
    proxies = _nodes_to_proxies(nodes)
    if not proxies:
        return [TestResult(
            node_id=n.id,
            node_key=n.node_key,
            alive=False,
            error="无法转换为 Mihomo proxy",
            test_mode="mihomo",
        ) for n in nodes if not n.clash_proxy]

    results: list[TestResult] = []

    try:
        # 启动 Mihomo
        if not manager.start(proxies):
            logger.error("Mihomo 启动失败，跳过本批次")
            return [TestResult(
                node_id=n.id,
                node_key=n.node_key,
                alive=False,
                error="Mihomo 启动失败",
                test_mode="mihomo",
            ) for n in nodes]

        # 逐个测试
        for i, node in enumerate(nodes):
            if node.clash_proxy is None:
                results.append(TestResult(
                    node_id=node.id,
                    node_key=node.node_key,
                    alive=False,
                    error="无法转换为 Mihomo proxy",
                    test_mode="mihomo",
                ))
                continue

            proxy_name = node.clash_proxy.get("name", node.name)

            alive, latency, error = manager.test_proxy_delay(
                proxy_name,
                timeout=config.tester.timeout * 1000,
                url=config.tester.test_url,
            )

            result = TestResult(
                node_id=node.id,
                node_key=node.node_key,
                alive=alive,
                latency=latency,
                error=error,
                test_mode="mihomo",
            )
            results.append(result)

            if on_progress:
                current = batch_offset + i + 1
                status = f"✓ {latency}ms" if alive else f"✗ {error[:30]}"
                on_progress(current, total, f"{node.node_key} - {status}")

    except Exception as e:
        logger.error(f"Mihomo 批次测试异常: {e}")
        # 为未测试的节点生成失败结果
        tested_keys = {r.node_key for r in results}
        for node in nodes:
            if node.node_key not in tested_keys:
                results.append(TestResult(
                    node_id=node.id,
                    node_key=node.node_key,
                    alive=False,
                    error=f"Mihomo 批次异常: {e}",
                    test_mode="mihomo",
                ))
    finally:
        # 确保 Mihomo 被停止
        manager.stop()

    return results
