# path: freeladder/tasks/fetch_pipeline.py
"""多线程一键获取 Pipeline

从 SourceIntelEngine 和 legacy 源并发抓取节点，
通过 DBWriter 单写入线程入库，避免 SQLite 多线程锁。

流程:
1. 从 SourceIntelEngine 获取 enabled 源
2. 如果 scraper.builtin_enabled=true，追加 legacy BUILTIN_SOURCES
3. 过滤失败缓存
4. ThreadPoolExecutor 并发抓取
5. 限制 max_pending_futures，不能一次性提交无限 future
6. 单源最多 max_nodes_per_source
7. 总节点最多 max_total_nodes_per_task
8. 节点批次送入 DBWriter
9. 支持 cancel_token
10. 返回统计
"""

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable, Optional

from loguru import logger

from freeladder.core.cancel_token import CancelToken
from freeladder.scraper.scraper import scrape_source, _is_source_failed, _mark_source_failed
from .db_writer import DBWriter
from .progress import ProgressThrottler


def run_fetch_pipeline(
    db,
    on_progress: Optional[Callable] = None,
    cancel_token: Optional[CancelToken] = None,
    config=None,
) -> dict:
    """多线程一键获取

    Args:
        db: Database 实例
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
    scraper_cfg = config.scraper

    stats = {
        "sources_total": 0,
        "sources_done": 0,
        "sources_failed": 0,
        "raw_nodes": 0,
        "submitted_nodes": 0,
        "inserted": 0,
        "updated": 0,
        "cancelled": False,
    }

    throttler = ProgressThrottler(perf.progress_update_interval_ms)

    # 1. 收集启用的源
    sources = []
    try:
        from freeladder.source_intel.engine import SourceIntelEngine
        si_config = config.source_intel
        if si_config.enabled:
            engine = SourceIntelEngine(si_config)
            enabled_urls = engine.get_enabled_source_urls()
            if enabled_urls:
                sources.extend(enabled_urls)
                logger.info(f"从 source_intel 获取 {len(enabled_urls)} 个启用源")
    except Exception as e:
        logger.debug(f"source_intel 未加载: {e}")

    if scraper_cfg.builtin_enabled:
        try:
            from freeladder.core.builtin_sources import BUILTIN_SOURCES
            legacy_urls = [s["url"] for s in BUILTIN_SOURCES]
            sources.extend(legacy_urls)
            logger.info(f"追加 {len(legacy_urls)} 个 legacy 内置源")
        except Exception as e:
            logger.debug(f"加载 legacy 源失败: {e}")

    stats["sources_total"] = len(sources)
    if not sources:
        logger.warning("没有启用的源，请先在源情报中心启用源")
        return stats

    # 2. 过滤失败缓存
    cache_minutes = scraper_cfg.source_failure_cache_minutes
    active_sources = [u for u in sources if not _is_source_failed(u, cache_minutes)]
    skipped = len(sources) - len(active_sources)
    if skipped:
        logger.info(f"跳过 {skipped} 个近期失败的源")

    if not active_sources:
        logger.warning("所有源均在失败缓存中")
        stats["sources_failed"] = len(sources)
        return stats

    # 3. 启动 DBWriter
    db_writer = DBWriter(
        db,
        batch_size=perf.db_batch_size,
        queue_max_size=perf.db_queue_max_size,
    )
    db_writer.start(cancel_token=cancel_token)

    # 4. 并发抓取
    max_workers = min(perf.fetch_workers, len(active_sources))
    max_per_source = perf.max_nodes_per_source
    max_total = perf.max_total_nodes_per_task
    timeout = perf.source_timeout_seconds
    submitted_total = 0

    def _fetch_one(url: str) -> tuple[str, list]:
        """抓取单个源"""
        if cancel_token and cancel_token.cancelled:
            return url, []
        try:
            nodes = scrape_source(url, timeout)
            if len(nodes) > max_per_source:
                nodes = nodes[:max_per_source]
            return url, nodes
        except Exception as e:
            logger.debug(f"源抓取失败 {url}: {e}")
            _mark_source_failed(url)
            return url, []

    try:
        with ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="fetch") as executor:
            futures = {executor.submit(_fetch_one, u): u for u in active_sources}
            done_count = 0

            for future in as_completed(futures):
                if cancel_token and cancel_token.cancelled:
                    for f in futures:
                        f.cancel()
                    stats["cancelled"] = True
                    break

                try:
                    url, nodes = future.result()
                except Exception as e:
                    logger.debug(f"Future 异常: {e}")
                    done_count += 1
                    stats["sources_failed"] += 1
                    continue

                done_count += 1
                stats["sources_done"] = done_count

                if nodes:
                    stats["raw_nodes"] += len(nodes)
                    # 检查总量限制
                    remaining = max_total - submitted_total
                    if remaining <= 0:
                        logger.info(f"达到总节点上限 {max_total}，停止提交")
                        for f in futures:
                            f.cancel()
                        stats["cancelled"] = True
                        break

                    nodes_to_submit = nodes[:remaining]
                    db_writer.submit_nodes(nodes_to_submit)
                    submitted_total += len(nodes_to_submit)
                    stats["submitted_nodes"] = submitted_total
                else:
                    stats["sources_failed"] += 1

                # 节流进度
                if on_progress and throttler.should_emit():
                    on_progress(done_count, stats["sources_total"], f"已完成 {done_count}/{stats['sources_total']} 个源")

    except Exception as e:
        logger.error(f"FetchPipeline 异常: {e}")

    # 5. 等待 DBWriter 完成
    db_writer.flush()
    db_writer.wait(timeout=30)

    stats["inserted"] = db_writer.stats.inserted
    stats["updated"] = db_writer.stats.updated

    logger.info(
        f"FetchPipeline 完成: {stats['sources_done']}/{stats['sources_total']} 源, "
        f"原始 {stats['raw_nodes']} 节点, 提交 {stats['submitted_nodes']}, "
        f"新增 {stats['inserted']}, 更新 {stats['updated']}"
    )

    return stats
