# path: freeladder/exporter/clash_exporter.py
"""Clash / Mihomo YAML 配置导出模块"""

import time
from pathlib import Path
from typing import Optional

import yaml
from loguru import logger

from freeladder.core.config import get_config
from freeladder.core.database import Database, get_db
from freeladder.core.models import Node, ExportOptions
from freeladder.core.utils import make_unique_proxy_names


def _is_valid_proxy(proxy: dict) -> bool:
    """校验 proxy dict 是否包含必要字段"""
    if not isinstance(proxy, dict):
        return False
    if not proxy.get("name"):
        return False
    if not proxy.get("type"):
        return False
    if not proxy.get("server"):
        return False
    try:
        port = int(proxy.get("port", 0))
    except (TypeError, ValueError):
        return False
    return 0 < port <= 65535


def _build_clash_config(nodes: list[Node]) -> dict:
    """构建 Clash/Mihomo YAML 配置

    过滤无效 proxy，唯一化 proxy names。
    """
    raw_proxies = []
    for node in nodes:
        if node.clash_proxy:
            raw_proxies.append(node.clash_proxy)

    # 过滤无效 proxy
    valid_proxies = []
    for p in raw_proxies:
        if _is_valid_proxy(p):
            valid_proxies.append(p)
        else:
            logger.debug(f"导出跳过无效 proxy: {p.get('name', '?')}")

    if not valid_proxies:
        return {"port": 7890, "socks-port": 7891, "allow-lan": False,
                "mode": "rule", "log-level": "info", "proxies": [],
                "proxy-groups": [], "rules": ["MATCH,DIRECT"]}

    # 唯一化 proxy names
    unique_proxies = make_unique_proxy_names(valid_proxies)
    proxy_names = [p["name"] for p in unique_proxies]

    config = {
        "port": 7890,
        "socks-port": 7891,
        "allow-lan": False,
        "mode": "rule",
        "log-level": "info",
        "proxies": unique_proxies,
        "proxy-groups": [
            {
                "name": "Auto",
                "type": "url-test",
                "proxies": proxy_names,
                "url": "https://www.gstatic.com/generate_204",
                "interval": 300,
            },
            {
                "name": "Proxy",
                "type": "select",
                "proxies": ["Auto", "DIRECT"] + proxy_names,
            },
        ],
        "rules": [
            "MATCH,Proxy"
        ],
    }

    return config


def export_clash_yaml(
    options: Optional[ExportOptions] = None,
    db: Optional[Database] = None,
) -> str:
    """导出 Clash/Mihomo YAML 配置

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

    if not nodes:
        logger.warning("没有符合条件的节点可导出")
        return ""

    # 生成配置
    clash_config = _build_clash_config(nodes)

    # 确定输出路径
    export_dir = config.export_path
    if options.filename:
        filename = options.filename
    else:
        filename = f"clash_{time.strftime('%Y%m%d_%H%M%S')}.yaml"

    output_path = export_dir / filename

    # 写入文件
    with open(output_path, "w", encoding="utf-8") as f:
        yaml.dump(clash_config, f, default_flow_style=False, allow_unicode=True)

    logger.info(f"Clash 配置已导出: {output_path} ({len(nodes)} 个节点)")
    return str(output_path)


def get_clash_yaml_string(
    nodes: list[Node],
) -> str:
    """将节点列表转为 Clash YAML 字符串（不写文件）"""
    config = _build_clash_config(nodes)
    return yaml.dump(config, default_flow_style=False, allow_unicode=True)
