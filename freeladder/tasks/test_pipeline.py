# path: freeladder/tasks/test_pipeline.py
"""多线程节点测试 Pipeline

多线程测试节点，测试结果分批写库，GUI 不实时重绘整表。

流程:
1. 根据 mode 获取待测试节点
2. 普通测试用 test_workers 并发
3. 测试结果收集到列表，每 batch_size 条写一次库
4. 支持 cancel_token
"""

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable, Optional

from loguru import logger

from freeladder.core.cancel_token import CancelToken
from .progress import ProgressThrottler


def run_test_pipeline(
    db,
    mode: str = "new",
    on_progress: Optional[Callable] = None,
    cancel_token: Optional[CancelToken] = None,
    config=None,
) -> dict:
    """多线程节点测试

    Args:
        db: Database 实例
        mode: 测试模式 new/alive/all
        on_progress: 进度回调 (current, total, message)
        cancel_token: 取消令牌
        config: 配置对象（可选）

    Returns:
        统计信息字典
    """
    from freeladder.core.config import get_config

    if config is None:
        config = get_config()

    perf = config.performance
    throttler = ProgressThrottler(perf.progress_update_interval_ms)

    stats = {
        "total": 0,
        "tested": 0,
        "alive": 0,
        "dead": 0,
        "cancelled": False,
    }

    # 1. 获取待测试节点
    try:
        if mode == "new":
            nodes = db.get_nodes_page(offset=0, limit=perf.max_total_nodes_per_task, alive_only=False)
            nodes = [n for n in nodes if not n.last_checked]
        elif mode == "alive":
            nodes = db.get_nodes_page(offset=0, limit=perf.max_total_nodes_per_task, alive_only=True)
        else:  # all
            nodes = db.get_nodes_page(offset=0, limit=perf.max_total_nodes_per_task)
    except Exception as e:
        logger.error(f"获取待测试节点失败: {e}")
        return stats

    stats["total"] = len(nodes)
    if not nodes:
        logger.info("没有需要测试的节点")
        return stats

    # 2. 并发测试，结果收集后批量写库
    max_workers = min(perf.test_workers, len(nodes))
    timeout = perf.test_timeout_seconds
    batch_size = perf.db_batch_size
    results_batch = []

    def _test_one(node):
        """测试单个节点"""
        if cancel_token and cancel_token.cancelled:
            return node, False, -1, ""

        try:
            from freeladder.tester import TestService
            tester = TestService(db)
            result = tester.test_single_node(node, timeout=timeout)
            return node, result.alive, result.latency, result.error
        except Exception as e:
            return node, False, -1, str(e)

    def _flush_batch(batch):
        """批量写入测试结果"""
        if not batch:
            return
        try:
            db.upsert_nodes_bulk(batch, batch_size=batch_size)
        except Exception as e:
            logger.debug(f"批量写入测试结果失败: {e}")

    try:
        with ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="test") as executor:
            futures = {executor.submit(_test_one, n): n for n in nodes}
            done_count = 0

            for future in as_completed(futures):
                if cancel_token and cancel_token.cancelled:
                    for f in futures:
                        f.cancel()
                    stats["cancelled"] = True
                    break

                try:
                    node, alive, latency, error = future.result()
                except Exception as e:
                    done_count += 1
                    stats["dead"] += 1
                    continue

                done_count += 1
                stats["tested"] = done_count

                if alive:
                    stats["alive"] += 1
                else:
                    stats["dead"] += 1

                # 更新节点状态并加入批量
                node.alive = alive
                node.latency = latency if latency > 0 else None
                node.last_checked = time.strftime("%Y-%m-%d %H:%M:%S")
                results_batch.append(node)

                # 达到 batch_size 时写库
                if len(results_batch) >= batch_size:
                    _flush_batch(results_batch)
                    results_batch = []

                if on_progress and throttler.should_emit():
                    on_progress(done_count, stats["total"], f"测试 {done_count}/{stats['total']} 个节点")

    except Exception as e:
        logger.error(f"TestPipeline 异常: {e}")

    # 写入剩余
    _flush_batch(results_batch)

    logger.info(
        f"TestPipeline 完成: 测试 {stats['tested']}, 可用 {stats['alive']}, 失败 {stats['dead']}"
    )

    return stats
