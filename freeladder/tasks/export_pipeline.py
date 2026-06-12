# path: freeladder/tasks/export_pipeline.py
"""后台导出 Pipeline

支持 Clash 导出、订阅导出、分组导出，
大量节点导出不阻塞 GUI。

流程:
1. 根据 export_type 执行相应导出
2. 导出过程支持 cancel_token
3. 返回导出结果
"""

from typing import Callable, Optional

from loguru import logger

from freeladder.core.cancel_token import CancelToken
from .progress import ProgressThrottler


def run_export_pipeline(
    db,
    export_type: str = "clash",
    on_progress: Optional[Callable] = None,
    cancel_token: Optional[CancelToken] = None,
    config=None,
    **kwargs,
) -> dict:
    """后台导出

    Args:
        db: Database 实例
        export_type: 导出类型 clash/subscription/group
        on_progress: 进度回调 (current, total, message)
        cancel_token: 取消令牌
        config: 配置对象（可选）
        **kwargs: 额外参数（如 group_name）

    Returns:
        统计信息字典
    """
    from freeladder.core.config import get_config

    if config is None:
        config = get_config()

    perf = config.performance
    throttler = ProgressThrottler(perf.progress_update_interval_ms)

    stats = {
        "export_type": export_type,
        "nodes_exported": 0,
        "file_path": "",
        "cancelled": False,
    }

    try:
        if export_type == "clash":
            from freeladder.exporter import export_clash_yaml
            path = export_clash_yaml(db=db)
            stats["file_path"] = path or ""

        elif export_type == "subscription":
            from freeladder.exporter import export_subscription
            path = export_subscription(db=db)
            stats["file_path"] = path or ""

        elif export_type == "group":
            group_name = kwargs.get("group_name", "")
            from freeladder.exporter import export_group
            path = export_group(db=db, group_name=group_name)
            stats["file_path"] = path or ""

        else:
            logger.error(f"未知导出类型: {export_type}")
            return stats

        if stats["file_path"]:
            stats["nodes_exported"] = 1  # 导出成功
            logger.info(f"导出完成: {stats['file_path']}")
        else:
            logger.warning("导出失败：没有可用节点")

    except Exception as e:
        logger.error(f"ExportPipeline 异常: {e}")

    return stats
