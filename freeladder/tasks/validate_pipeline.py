# path: freeladder/tasks/validate_pipeline.py
"""多线程源验证 Pipeline

多线程验证候选源，写回 SourceStore 健康状态。

流程:
1. 获取 candidate/stale/failed 但未 dead 的源
2. 使用 ThreadPoolExecutor 并发验证
3. 写回 SourceStore 健康状态
4. 支持 cancel_token
5. 进度节流
"""

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable, Optional

from loguru import logger

from freeladder.core.cancel_token import CancelToken
from freeladder.source_intel.models import SourceStatus
from .progress import ProgressThrottler


def run_validate_pipeline(
    store,
    validator,
    health,
    on_progress: Optional[Callable] = None,
    cancel_token: Optional[CancelToken] = None,
    config=None,
) -> dict:
    """多线程源验证

    Args:
        store: SourceStore 实例
        validator: SourceValidator 实例
        health: SourceHealth 实例
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
        "validated": 0,
        "failed": 0,
        "cancelled": False,
    }

    # 1. 检查取消状态
    if cancel_token and cancel_token.cancelled:
        stats["cancelled"] = True
        return stats

    # 2. 获取候选源
    candidates = store.list_candidates()
    # 过滤 DEAD 源
    candidates = [s for s in candidates if s.status != SourceStatus.DEAD]
    stats["total"] = len(candidates)

    if not candidates:
        logger.info("没有需要验证的候选源")
        return stats

    # 2. 检查取消状态
    if cancel_token and cancel_token.cancelled:
        stats["cancelled"] = True
        return stats

    # 3. 并发验证
    max_workers = min(perf.validate_workers, len(candidates))

    def _validate_one(source):
        """验证单个源"""
        if cancel_token and cancel_token.cancelled:
            return None, False, ""

        try:
            result = validator.validate(source)
            if result.get("valid"):
                source = health.update_after_success(
                    source, result.get("node_count", 0), result.get("protocol_stats", {})
                )
                return source, True, ""
            else:
                source = health.update_after_failure(source, result.get("error", "未知错误"))
                return source, False, result.get("error", "未知错误")
        except Exception as e:
            source = health.update_after_failure(source, str(e))
            return source, False, str(e)

    try:
        with ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="validate") as executor:
            futures = {executor.submit(_validate_one, s): s for s in candidates}
            done_count = 0

            for future in as_completed(futures):
                if cancel_token and cancel_token.cancelled:
                    for f in futures:
                        f.cancel()
                    stats["cancelled"] = True
                    break

                try:
                    source, ok, error = future.result()
                except Exception as e:
                    done_count += 1
                    stats["failed"] += 1
                    continue

                done_count += 1

                if source:
                    store.upsert_source(source)

                if ok:
                    stats["validated"] += 1
                else:
                    stats["failed"] += 1

                if on_progress and throttler.should_emit():
                    on_progress(done_count, stats["total"], f"验证 {done_count}/{stats['total']} 个源")

    except Exception as e:
        logger.error(f"ValidatePipeline 异常: {e}")

    logger.info(
        f"ValidatePipeline 完成: 验证 {stats['validated']}, 失败 {stats['failed']}"
    )

    return stats
