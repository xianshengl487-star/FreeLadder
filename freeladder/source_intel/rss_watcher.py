# path: freeladder/source_intel/rss_watcher.py
"""RSS / Atom 监控器

从公开 RSS/Atom feed 中提取候选订阅地址。
"""

import time
from typing import Optional
from xml.etree import ElementTree

import httpx
from loguru import logger

from .models import SourceRecord, SourceKind
from .source_store import SourceStore
from .link_extractor import LinkExtractor


class RSSWatcher:
    """RSS / Atom 监控器"""

    def __init__(self, store: SourceStore, config=None, extractor: Optional[LinkExtractor] = None):
        if config is None:
            from freeladder.core.config import get_config
            config = get_config().source_intel
        self._config = config
        self._store = store
        self._extractor = extractor or LinkExtractor()

    def check_feed(self, feed_url: str) -> list[SourceRecord]:
        """检查单个 feed"""
        headers = {"User-Agent": self._config.user_agent}
        timeout = self._config.request_timeout_seconds
        max_bytes = self._config.max_download_mb * 1024 * 1024

        try:
            with httpx.Client(timeout=timeout, follow_redirects=True) as client:
                resp = client.get(feed_url, headers=headers)
                if resp.status_code == 304:
                    return []
                resp.raise_for_status()

                content = resp.text
                if len(content.encode("utf-8")) > max_bytes:
                    logger.warning(f"Feed 内容过大: {feed_url}")
                    return []

                return self._parse_feed(content, feed_url)
        except Exception as e:
            logger.debug(f"检查 feed 失败 {feed_url}: {e}")
            return []

    def check_all(self, feeds: list[str], on_progress=None, cancel_token=None) -> list[SourceRecord]:
        """检查所有 feeds"""
        all_sources = []
        total = len(feeds)

        for i, feed_url in enumerate(feeds, 1):
            if cancel_token and cancel_token.cancelled:
                break

            sources = self.check_feed(feed_url)
            all_sources.extend(sources)

            if on_progress:
                on_progress(i, total, f"检查 {feed_url[:40]}")

            time.sleep(1)

        return all_sources

    def _parse_feed(self, content: str, feed_url: str) -> list[SourceRecord]:
        """解析 RSS/Atom feed"""
        sources = []
        try:
            root = ElementTree.fromstring(content)
        except ElementTree.ParseError:
            return []

        # 提取所有文本内容和链接
        for elem in root.iter():
            # 提取链接
            if elem.tag in ("link", "{http://www.w3.org/2005/Atom}link"):
                href = elem.get("href", "") or (elem.text or "")
                if href:
                    extracted = self._extractor.extract_from_text(
                        href, discovered_from=f"rss:{feed_url}"
                    )
                    sources.extend(extracted)

            # 提取标题和摘要中的 URL
            if elem.text:
                extracted = self._extractor.extract_from_text(
                    elem.text, discovered_from=f"rss:{feed_url}"
                )
                sources.extend(extracted)

            # 提取描述/内容
            if elem.tag in ("description", "{http://www.w3.org/2005/Atom}summary",
                           "{http://www.w3.org/2005/Atom}content"):
                if elem.text:
                    extracted = self._extractor.extract_from_text(
                        elem.text, discovered_from=f"rss:{feed_url}"
                    )
                    sources.extend(extracted)

        # 去重
        seen = set()
        unique = []
        for s in sources:
            if s.url not in seen:
                seen.add(s.url)
                unique.append(s)

        logger.debug(f"从 {feed_url} 提取到 {len(unique)} 个候选源")
        return unique
