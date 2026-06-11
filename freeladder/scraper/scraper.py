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
from .sources import load_sources, decode_subscription_content, extract_uris_from_yaml


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
    """从单个订阅源获取并解析节点"""
    logger.info(f"正在获取订阅源: {url}")
    content = _fetch_url(url, timeout)
    if not content:
        return []

    # 检测是否是 YAML 格式
    stripped = content.strip()
    if stripped.startswith('{') or stripped.startswith('proxies:'):
        # 可能是 JSON 或 Clash YAML
        if stripped.startswith('{'):
            # JSON -> 尝试转为文本提取 URI
            pass  # 让解析器处理
        else:
            uris = extract_uris_from_yaml(stripped)
            if uris:
                text_content = '\n'.join(uris)
                nodes = parse_nodes_from_text(text_content)
                if nodes:
                    logger.info(f"从 YAML 订阅源获取 {len(nodes)} 个节点: {url}")
                    return nodes

    # 解码内容（自动检测 base64）
    decoded = decode_subscription_content(content)
    if not decoded:
        logger.warning(f"订阅源解码失败: {url}")
        return []

    # 再次检测 YAML
    decoded_stripped = decoded.strip()
    if decoded_stripped.startswith('proxies:'):
        uris = extract_uris_from_yaml(decoded_stripped)
        if uris:
            text_content = '\n'.join(uris)
            nodes = parse_nodes_from_text(text_content)
            if nodes:
                logger.info(f"从 YAML 订阅源获取 {len(nodes)} 个节点: {url}")
                return nodes

    # 按行解析 URI
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
