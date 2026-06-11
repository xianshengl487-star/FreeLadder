# path: freeladder/core/dedup.py
"""节点去重模块"""

import hashlib
from typing import Optional

from .models import Node


def deduplicate_nodes(nodes: list[Node]) -> list[Node]:
    """对节点列表去重

    去重策略:
    1. 按 node_key (protocol://server:port) 去重
    2. 按 raw_hash (raw_uri 的 MD5) 辅助去重
    3. 保留最新的节点
    """
    seen_keys: dict[str, Node] = {}
    seen_hashes: set[str] = set()
    result: list[Node] = []

    for node in nodes:
        if not node.server or not node.port:
            continue

        # 按 node_key 去重
        key = node.node_key
        if key in seen_keys:
            # 保留 raw_uri 更长的（信息更完整）
            existing = seen_keys[key]
            if len(node.raw_uri) > len(existing.raw_uri):
                result.remove(existing)
                seen_keys[key] = node
                raw_hash = node.raw_hash
                if raw_hash not in seen_hashes:
                    seen_hashes.add(raw_hash)
                    result.append(node)
            continue

        # 按 raw_hash 去重
        raw_hash = node.raw_hash
        if raw_hash in seen_hashes:
            continue

        seen_keys[key] = node
        seen_hashes.add(raw_hash)
        result.append(node)

    return result


def generate_node_key(protocol: str, server: str, port: int) -> str:
    """生成节点唯一标识"""
    return f"{protocol}://{server}:{port}"


def generate_raw_hash(raw_uri: str) -> str:
    """生成 raw_uri 的 MD5 哈希"""
    if raw_uri:
        return hashlib.md5(raw_uri.encode()).hexdigest()
    return ""
