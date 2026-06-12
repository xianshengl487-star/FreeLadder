# path: freeladder/source_intel/non_github_discovery.py
"""非 GitHub 公开源候选发现

发现 GitHub 以外的公开免费源候选入口，全部默认 disabled。

来源:
- 用户手动配置的公开网页
- 用户手动配置的公开 RSS / Atom
- 项目内预置的"候选入口模板"
- 公开网页中明示展示的订阅链接

禁止:
- 默认全网搜索
- 默认访问大量网站
- 默认深度爬取
- 绕过 Cloudflare / 验证码
- 模拟登录
- 抓取私有 Telegram/Discord
- 猜测订阅路径
"""

import time
from typing import Optional

import httpx
from loguru import logger

from .models import SourceRecord, SourceKind
from .source_store import SourceStore
from .link_extractor import LinkExtractor

# 不可访问的地址模式
_BLOCKED_HOSTS = {"localhost", "127.0.0.1", "::1", "0.0.0.0"}
_BLOCKED_IP_PREFIXES = ("10.", "172.16.", "172.17.", "172.18.", "172.19.",
                        "172.20.", "172.21.", "172.22.", "172.23.", "172.24.",
                        "172.25.", "172.26.", "172.27.", "172.28.", "172.29.",
                        "172.30.", "172.31.", "192.168.")

# 预置候选公开页面（默认全部 disabled）
SEED_PUBLIC_PAGES: list[dict] = [
    {
        "name": "NodeFree",
        "url": "https://nodefree.org/",
        "kind": "webpage",
        "enabled": False,
        "note": "公开免费节点页面，扫描页面中明示的订阅地址",
    },
    {
        "name": "OpenRunner",
        "url": "https://freenode.openrunner.net/",
        "kind": "webpage",
        "enabled": False,
        "note": "公开 free node 页面，需从页面中提取明示 YAML 链接",
    },
    {
        "name": "Xrayfree",
        "url": "https://tt.vg/freeclash",
        "kind": "webpage",
        "enabled": False,
        "note": "公开免费 Clash 入口，需验证是否能解析为订阅内容",
    },
    {
        "name": "Learnhard-jsdelivr",
        "url": "https://cdn.jsdelivr.net/gh/vxiaov/free_proxies@main/clash/clash.provider.yaml",
        "kind": "jsdelivr",
        "enabled": False,
        "note": "jsDelivr GitHub CDN 镜像，Clash provider YAML",
    },
    {
        "name": "Pawdroid-mirror-v2gh",
        "url": "https://mirror.v2gh.com/https://raw.githubusercontent.com/Pawdroid/Free-servers/main/sub",
        "kind": "direct",
        "enabled": False,
        "note": "Pawdroid Free-servers 的公开镜像订阅入口",
    },
    {
        "name": "jsDelivr-mfuu",
        "url": "https://cdn.jsdelivr.net/gh/mfuu/v2ray@master/clash.yaml",
        "kind": "jsdelivr",
        "enabled": False,
        "note": "jsDelivr CDN 镜像，mfuu v2ray Clash 格式",
    },
    {
        "name": "jsDelivr-Pawdroid",
        "url": "https://cdn.jsdelivr.net/gh/Pawdroid/Free-servers@main/sub",
        "kind": "jsdelivr",
        "enabled": False,
        "note": "jsDelivr CDN 镜像，Pawdroid Free-servers Base64",
    },
    {
        "name": "ghproxy-mfuu",
        "url": "https://ghproxy.com/https://raw.githubusercontent.com/mfuu/v2ray/master/clash.yaml",
        "kind": "direct",
        "enabled": False,
        "note": "ghproxy GitHub 代理镜像",
    },
]


class NonGitHubDiscovery:
    """非 GitHub 公开源候选发现"""

    def __init__(self, store: SourceStore, config=None, extractor: Optional[LinkExtractor] = None):
        if config is None:
            from freeladder.core.config import get_config
            config = get_config().source_intel
        self._config = config
        self._store = store
        self._extractor = extractor or LinkExtractor()

    def discover_from_sites(
        self,
        sites: list[dict],
        on_progress=None,
        cancel_token=None,
    ) -> list[SourceRecord]:
        """从站点列表发现候选源"""
        all_sources = []
        active_sites = [s for s in sites if s.get("enabled", False)]
        active_sites = active_sites[:self._config.max_sites_per_run]

        if not active_sites:
            logger.info("没有启用的非 GitHub 站点")
            return []

        total = len(active_sites)
        for i, site in enumerate(active_sites, 1):
            if cancel_token and cancel_token.cancelled:
                break

            url = site.get("url", "")
            if not url:
                continue

            if self.should_skip_url(url):
                logger.debug(f"跳过不可访问地址: {url}")
                continue

            try:
                content = self.fetch_page(url)
                if content:
                    sources = self.scan_html(content, url)
                    # 限制每站提取数量
                    sources = sources[:self._config.max_links_per_site]
                    all_sources.extend(sources)
            except Exception as e:
                logger.debug(f"扫描站点失败 {url}: {e}")

            if on_progress:
                on_progress(i, total, f"扫描 {site.get('name', url[:30])}")

            # 限速
            time.sleep(1)

        return all_sources

    def fetch_page(self, url: str) -> str:
        """获取页面内容"""
        headers = {"User-Agent": self._config.user_agent}
        timeout = self._config.request_timeout_seconds
        max_bytes = self._config.max_download_mb * 1024 * 1024

        try:
            with httpx.Client(timeout=timeout, follow_redirects=True) as client:
                resp = client.get(url, headers=headers)
                resp.raise_for_status()

                # 检查大小
                content_length = resp.headers.get("content-length")
                if content_length and int(content_length) > max_bytes:
                    logger.warning(f"页面内容过大: {url}")
                    return ""

                content = resp.text
                if len(content.encode("utf-8")) > max_bytes:
                    return ""

                return content
        except Exception as e:
            logger.debug(f"获取页面失败 {url}: {e}")
            return ""

    def scan_html(self, html: str, base_url: str) -> list[SourceRecord]:
        """扫描 HTML 提取候选源"""
        return self._extractor.extract_from_html(html, base_url)

    def should_skip_url(self, url: str) -> bool:
        """检查 URL 是否应该跳过"""
        from urllib.parse import urlparse

        try:
            parsed = urlparse(url)
            host = (parsed.hostname or "").lower()

            if host in _BLOCKED_HOSTS:
                return True
            if host.startswith(_BLOCKED_IP_PREFIXES):
                return True
            if host.endswith(".onion"):
                return True

            # 只允许 http/https
            if parsed.scheme not in ("http", "https"):
                return True

            return False
        except Exception:
            return True

    def get_seed_public_pages(self) -> list[dict]:
        """获取预置候选公开页面列表（默认全部 disabled）"""
        return SEED_PUBLIC_PAGES
