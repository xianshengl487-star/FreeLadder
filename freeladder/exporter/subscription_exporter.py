# path: freeladder/exporter/subscription_exporter.py
"""Base64 订阅导出模块"""

import base64
import time
from pathlib import Path
from typing import Optional

from loguru import logger

from freeladder.core.config import get_config
from freeladder.core.database import Database, get_db
from freeladder.core.models import Node, ExportOptions


def export_subscription(
    options: Optional[ExportOptions] = None,
    db: Optional[Database] = None,
) -> str:
    """导出 Base64 订阅文件

    将节点 raw_uri 列表 base64 编码后导出。

    Args:
        options: 导出选项
        db: 数据库实例

    Returns:
        导出文件路径
    """
    config = get_config()
    db = db or get_db()

    if options is None:
        options = ExportOptions()

    # 获取节点
    if options.alive_only:
        nodes = db.get_alive_nodes()
    else:
        nodes = db.get_all_nodes()

    # 按协议筛选
    if options.protocols:
        nodes = [n for n in nodes if n.protocol.value in options.protocols]

    # 按分数筛选
    if options.min_score > 0:
        nodes = [n for n in nodes if n.score >= options.min_score]

    # 按分数排序
    nodes.sort(key=lambda n: n.score, reverse=True)

    # 限制节点数
    if options.max_nodes > 0:
        nodes = nodes[:options.max_nodes]

    # 收集有 raw_uri 的节点
    uris = [n.raw_uri for n in nodes if n.raw_uri]

    if not uris:
        logger.warning("没有可用的 raw_uri 可导出")
        return ""

    # 合并为文本
    text = "\n".join(uris)

    # Base64 编码
    encoded = base64.b64encode(text.encode("utf-8")).decode("utf-8")

    # 确定输出路径
    export_dir = config.export_path
    if options.filename:
        filename = options.filename
    else:
        filename = f"sub_{time.strftime('%Y%m%d_%H%M%S')}.txt"

    output_path = export_dir / filename

    # 写入文件
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(encoded)

    logger.info(f"订阅已导出: {output_path} ({len(uris)} 个节点)")
    return str(output_path)


def get_subscription_string(nodes: list[Node]) -> str:
    """将节点列表转为 Base64 订阅字符串（不写文件）"""
    uris = [n.raw_uri for n in nodes if n.raw_uri]
    text = "\n".join(uris)
    return base64.b64encode(text.encode("utf-8")).decode("utf-8")
