# path: freeladder/core/dedup.py
"""节点去重模块"""

import hashlib
from typing import Optional

from .models import Node


def deduplicate_nodes(nodes: list[Node]) -> list[Node]:
    """对节点列表去重

    去重策略:
    1. 按 node_key 去重（高级协议使用 raw_uri SHA256 哈希，普通协议使用 protocol://server:port）
    2. 保留信息更完整的节点（raw_uri 更长或 clash_proxy 更大）
    """
    by_key: dict[str, Node] = {}

    for node in nodes:
        if not node.server or not node.port:
            continue

        key = node.node_key
        old = by_key.get(key)

        if old is None:
            by_key[key] = node
            continue

        # 保留信息更完整的节点
        old_len = len(old.raw_uri or "") + len(str(old.clash_proxy or ""))
        new_len = len(node.raw_uri or "") + len(str(node.clash_proxy or ""))

        if new_len > old_len:
            by_key[key] = node

    return list(by_key.values())


def generate_node_key(protocol: str, server: str, port: int) -> str:
    """生成节点唯一标识"""
    return f"{protocol}://{server}:{port}"


def generate_raw_hash(raw_uri: str) -> str:
    """生成 raw_uri 的 SHA256 哈希"""
    if raw_uri:
        return hashlib.sha256(raw_uri.strip().encode("utf-8")).hexdigest()
    return ""
