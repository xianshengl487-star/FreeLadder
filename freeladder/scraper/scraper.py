# path: freeladder/scraper/scraper.py
"""爬取模块 - 从订阅源获取节点

支持:
- scrape_all():   从用户配置的订阅源爬取
- scrape_builtin(): 从内置免费订阅源爬取（并发 + 取消 + 限流）
"""

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
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
    extract_nodes_from_clash_yaml,
)

# 失败源缓存: {url: last_failure_time}
_failure_cache: dict[str, float] = {}


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
                _apply_countries(nodes)
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
                _apply_countries(nodes)
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

    _apply_countries(nodes)
    return nodes


def _apply_countries(nodes: list[Node]) -> None:
    """从节点名称提取国家/地区"""
    from freeladder.core.country_utils import apply_country_to_node
    for node in nodes:
        apply_country_to_node(node)


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


def _is_source_failed(url: str, cache_minutes: int) -> bool:
    """检查源是否在失败缓存中"""
    if url not in _failure_cache:
        return False
    elapsed = time.time() - _failure_cache[url]
    return elapsed < cache_minutes * 60


def _mark_source_failed(url: str):
    """标记源为失败"""
    _failure_cache[url] = time.time()


def scrape_builtin(
    on_progress: Optional[Callable[[int, int, str], None]] = None,
    cancel_token=None,
    max_total_nodes: Optional[int] = None,
) -> list[Node]:
    """从内置免费订阅源并发爬取节点

    特性:
    - 合并 legacy 内置源 + source_intel 启用源
    - ThreadPoolExecutor 并发爬取（受 max_workers 控制）
    - cancel_token 支持取消
    - max_total_nodes 限制总节点数
    - max_nodes_per_source 限制单源节点数
    - 失败源缓存避免频繁重试
    - 节流进度回调
    - DEAD 源自动跳过
    - 单源失败不影响整体

    Args:
        on_progress: 进度回调 (current, total, message)
        cancel_token: 取消令牌
        max_total_nodes: 最大总节点数（None 则使用配置值）
    """
    from freeladder.core.builtin_sources import BUILTIN_SOURCES

    config = get_config()
    scraper_cfg = config.scraper

    if max_total_nodes is None:
        max_total_nodes = scraper_cfg.max_total_nodes

    # 收集启用的源: 优先 source_intel，再追加 legacy builtin
    sources = []

    # 1. 从 source_intel 获取启用源
    try:
        from freeladder.source_intel.engine import SourceIntelEngine
        si_config = config.source_intel
        if si_config.enabled:
            engine = SourceIntelEngine(si_config)
            enabled_urls = engine.get_enabled_source_urls()
            if enabled_urls:
                logger.info(f"从 source_intel 获取 {len(enabled_urls)} 个启用源")
                sources.extend(enabled_urls)
    except Exception as e:
        logger.debug(f"source_intel 未加载: {e}")

    # 2. 仅当 builtin_enabled=true 时追加 legacy 内置源
    if scraper_cfg.builtin_enabled:
        legacy_urls = [s["url"] for s in BUILTIN_SOURCES]
        logger.info(f"追加 {len(legacy_urls)} 个 legacy 内置源")
        sources.extend(legacy_urls)

    if not sources:
        logger.warning("没有启用的源，请先在源情报中心启用源")
        return []

    timeout = scraper_cfg.request_timeout
    max_workers = min(scraper_cfg.max_workers, len(sources))
    cache_minutes = scraper_cfg.source_failure_cache_minutes
    max_per_source = scraper_cfg.max_nodes_per_source

    # 过滤失败缓存中的源
    active_sources = [u for u in sources if not _is_source_failed(u, cache_minutes)]
    skipped = len(sources) - len(active_sources)
    if skipped:
        logger.info(f"跳过 {skipped} 个近期失败的源")

    if not active_sources:
        logger.warning("所有源均在失败缓存中")
        return []

    all_nodes: list[Node] = []
    total = len(active_sources)

    def _fetch_one(url: str) -> tuple[str, list[Node]]:
        """爬取单个源（线程池中执行）"""
        if cancel_token and cancel_token.cancelled:
            return url, []
        try:
            nodes = scrape_source(url, timeout)
            # 限制单源节点数
            if len(nodes) > max_per_source:
                nodes = nodes[:max_per_source]
            return url, nodes
        except Exception as e:
            logger.debug(f"源爬取失败 {url}: {e}")
            _mark_source_failed(url)
            return url, []

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(_fetch_one, u): u for u in active_sources}
        done_count = 0

        for future in as_completed(futures):
            if cancel_token and cancel_token.cancelled:
                # 取消剩余任务
                for f in futures:
                    f.cancel()
                break

            url, nodes = future.result()
            done_count += 1

            if nodes:
                all_nodes.extend(nodes)

            if on_progress:
                on_progress(done_count, total, f"已完成 {done_count}/{total} 个源")

            # 总量限制
            if len(all_nodes) >= max_total_nodes:
                logger.info(f"达到总节点上限 {max_total_nodes}，停止爬取")
                # 取消剩余任务
                for f in futures:
                    f.cancel()
                break

    # 截断到上限
    if len(all_nodes) > max_total_nodes:
        all_nodes = all_nodes[:max_total_nodes]

    # 去重
    before = len(all_nodes)
    all_nodes = deduplicate_nodes(all_nodes)
    after = len(all_nodes)

    if before != after:
        logger.info(f"去重: {before} -> {after} 个节点")

    logger.info(f"从源共获取 {after} 个节点")
    return all_nodes
