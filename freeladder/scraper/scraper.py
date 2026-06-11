# path: freeladder/scraper/scraper.py
"""爬取模块 - 从订阅源获取节点"""

import base64
from typing import Callable, Optional

import httpx
from loguru import logger

from freeladder.core.config import get_config
from freeladder.core.models import Node
from freeladder.core.dedup import deduplicate_nodes
from .parser import parse_nodes_from_text
from .sources import (
    load_sources,
    decode_subscription_content,
    extract_uris_from_yaml,
    extract_nodes_from_clash_yaml,
)


def _fetch_url(url: str, timeout: int = 15) -> Optional[str]:
    """获取 URL 内容"""
    try:
        with httpx.Client(timeout=timeout, follow_redirects=True) as client:
            resp = client.get(url, headers={
                "User-Agent": "FreeLadder/1.0",
                "Accept": "*/*",
            })
            resp.raise_for_status()
            return resp.text
    except httpx.TimeoutException:
        logger.error(f"请求超时: {url}")
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP 错误 {e.response.status_code}: {url}")
    except Exception as e:
        logger.error(f"请求失败 {url}: {e}")
    return None


def scrape_source(url: str, timeout: int = 15) -> list[Node]:
    """从单个订阅源获取并解析节点

    解析策略:
    1. 如果内容是 Clash/Mihomo YAML (含 proxies 字段)，直接提取完整 proxy dict
    2. 否则尝试 base64 解码后按 URI 行解析
    3. 如果解码后仍是 Clash YAML，再次尝试完整提取
    """
    logger.info(f"正在获取订阅源: {url}")
    content = _fetch_url(url, timeout)
    if not content:
        return []

    stripped = content.strip()

    # 直接尝试 Clash YAML 解析（优先，保留完整 proxy 参数）
    if stripped.startswith('{') or stripped.startswith('proxies:') or 'proxies:' in stripped[:200]:
        try:
            import yaml
            yaml.safe_load(stripped)  # 验证是合法 YAML
            nodes = extract_nodes_from_clash_yaml(stripped)
            if nodes:
                logger.info(f"从 Clash YAML 订阅源获取 {len(nodes)} 个节点: {url}")
                return nodes
        except Exception:
            pass  # 不是合法 YAML，继续尝试其他方式

    # 解码内容（自动检测 base64）
    decoded = decode_subscription_content(content)
    if not decoded:
        logger.warning(f"订阅源解码失败: {url}")
        return []

    # 解码后也尝试 Clash YAML 解析
    decoded_stripped = decoded.strip()
    if decoded_stripped.startswith('{') or 'proxies:' in decoded_stripped[:200]:
        try:
            import yaml
            yaml.safe_load(decoded_stripped)  # 验证是合法 YAML
            nodes = extract_nodes_from_clash_yaml(decoded_stripped)
            if nodes:
                logger.info(f"从 Clash YAML 订阅源获取 {len(nodes)} 个节点: {url}")
                return nodes
        except Exception:
            pass

    # 按行解析 URI（普通文本/base64 订阅）
    nodes = parse_nodes_from_text(decoded)
    if nodes:
        logger.info(f"从订阅源获取 {len(nodes)} 个节点: {url}")
    else:
        logger.warning(f"订阅源未找到有效节点: {url}")

    return nodes


def scrape_all(
    on_progress: Optional[Callable[[int, int, str], None]] = None,
) -> list[Node]:
    """从所有配置的订阅源爬取节点"""
    sources = load_sources()
    if not sources:
        return []

    config = get_config()
    all_nodes: list[Node] = []
    total = len(sources)

    for i, url in enumerate(sources, 1):
        if on_progress:
            on_progress(i, total, f"正在获取: {url[:50]}...")

        try:
            nodes = scrape_source(url, config.scraper.request_timeout)
            all_nodes.extend(nodes)
        except Exception as e:
            logger.error(f"爬取失败 {url}: {e}")

    # 去重
    before = len(all_nodes)
    all_nodes = deduplicate_nodes(all_nodes)
    after = len(all_nodes)

    if before != after:
        logger.info(f"去重: {before} -> {after} 个节点")

    logger.info(f"共获取 {after} 个节点（来自 {total} 个源）")
    return all_nodes
