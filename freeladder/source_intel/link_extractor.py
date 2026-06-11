# path: freeladder/source_intel/link_extractor.py
"""链接提取器

从 README、YAML、TXT、HTML、RSS 内容中提取候选订阅源或直接节点。

安全要求:
- 不生成猜测路径
- 不爆破目录
- 不递归深挖
- 默认只提取当前页面明示链接
- 不执行页面 JavaScript
- 不绕过验证码
- 对明显不可用链接过滤 (localhost、内网地址、私有 IP)
- 对非常长的 data URL 直接丢弃
"""

import re
from urllib.parse import urljoin, urlparse

from loguru import logger

from .models import SourceRecord, SourceKind, SourceFormat, _make_source_id, _normalize_url


# 常见订阅文件名
SUBSCRIPTION_FILENAMES = {
    "sub", "sub.txt", "subs.txt", "subscribe",
    "clash.yaml", "clash.yml", "config.yaml", "proxy.yaml",
    "nodes.txt", "v2ray", "v2ray.txt", "base64",
}

# 协议 URI 前缀
PROTOCOL_URIS = (
    "vmess://", "vless://", "trojan://", "ss://", "ssr://",
    "hysteria://", "hysteria2://", "hy2://", "tuic://",
    "socks://", "socks5://",
)

# 不可访问的地址模式
_BLOCKED_HOSTS = {
    "localhost", "127.0.0.1", "::1", "0.0.0.0",
    "10.0.0.0", "172.16.0.0", "192.168.0.0",
}
_BLOCKED_IP_PREFIXES = ("10.", "172.16.", "172.17.", "172.18.", "172.19.",
                        "172.20.", "172.21.", "172.22.", "172.23.", "172.24.",
                        "172.25.", "172.26.", "172.27.", "172.28.", "172.29.",
                        "172.30.", "172.31.", "192.168.")

# Markdown 链接正则
_MD_LINK_RE = re.compile(r'\[([^\]]*)\]\(([^)]+)\)')
# HTML href 正则
_HREF_RE = re.compile(r'href=["\']([^"\']+)["\']', re.IGNORECASE)
# 纯 URL 正则
_URL_RE = re.compile(r'https?://[^\s<>"\')\]]+')
# URI 协议正则
_URI_RE = re.compile(
    r'(?:vmess|vless|trojan|ss|ssr|hysteria|hysteria2|hy2|tuic|socks|socks5)://[^\s<>"\')\]]+',
    re.IGNORECASE,
)


class LinkExtractor:
    """从文本/HTML 中提取候选订阅源链接"""

    def extract_from_text(self, text: str, discovered_from: str = "") -> list[SourceRecord]:
        """从纯文本/Markdown 提取候选源"""
        sources = []
        seen_urls = set()

        # 提取 Markdown 链接
        for match in _MD_LINK_RE.finditer(text):
            url = match.group(2).strip()
            url = self.normalize_url(url, discovered_from)
            if url and url not in seen_urls and self._is_usable_url(url):
                kind = self.guess_kind(url)
                fmt = self.guess_format(url)
                sources.append(SourceRecord(
                    id=_make_source_id(url),
                    name=self._name_from_url(url),
                    url=url,
                    kind=kind,
                    format=fmt,
                    discovered_from=discovered_from,
                ))
                seen_urls.add(url)

        # 提取纯 URL
        for match in _URL_RE.finditer(text):
            url = match.group(0).strip(".,;:!?")
            url = self.normalize_url(url, discovered_from)
            if url and url not in seen_urls and self._is_usable_url(url):
                kind = self.guess_kind(url)
                fmt = self.guess_format(url)
                sources.append(SourceRecord(
                    id=_make_source_id(url),
                    name=self._name_from_url(url),
                    url=url,
                    kind=kind,
                    format=fmt,
                    discovered_from=discovered_from,
                ))
                seen_urls.add(url)

        return sources

    def extract_from_html(self, html: str, base_url: str = "") -> list[SourceRecord]:
        """从 HTML 提取候选源"""
        sources = []
        seen_urls = set()

        for match in _HREF_RE.finditer(html):
            url = match.group(1).strip()
            if url.startswith(("#", "javascript:", "mailto:", "tel:")):
                continue
            url = self.normalize_url(url, base_url)
            if url and url not in seen_urls and self._is_usable_url(url):
                kind = self.guess_kind(url)
                fmt = self.guess_format(url)
                sources.append(SourceRecord(
                    id=_make_source_id(url),
                    name=self._name_from_url(url),
                    url=url,
                    kind=kind,
                    format=fmt,
                    discovered_from=base_url,
                ))
                seen_urls.add(url)

        return sources

    def extract_direct_nodes(self, text: str) -> list[str]:
        """提取直接节点 URI"""
        nodes = []
        seen = set()
        for match in _URI_RE.finditer(text):
            uri = match.group(0)
            if uri not in seen:
                nodes.append(uri)
                seen.add(uri)
        return nodes

    def normalize_url(self, url: str, base_url: str = "") -> str:
        """URL 归一化"""
        url = url.strip()
        if not url or url.startswith("data:"):
            return ""
        # 清理 Markdown 括号、引号、尾部标点
        url = re.sub(r'[`\s]+', '', url)
        url = url.rstrip(".,;:!?)")

        # 处理相对链接
        if base_url and not url.startswith(("http://", "https://")):
            url = urljoin(base_url, url)

        if not url.startswith(("http://", "https://")):
            return ""

        return _normalize_url(url)

    def guess_kind(self, url: str) -> SourceKind:
        """猜测源类型"""
        url_lower = url.lower()
        if "raw.githubusercontent.com" in url_lower:
            return SourceKind.GITHUB_RAW
        if "github.io" in url_lower:
            return SourceKind.GITHUB_PAGES
        if "jsdelivr.net" in url_lower:
            return SourceKind.JSDELIVR
        if "/rss" in url_lower or "/feed" in url_lower or "/atom" in url_lower:
            return SourceKind.RSS
        return SourceKind.DIRECT

    def guess_format(self, url: str, content_hint: str = "") -> SourceFormat:
        """猜测源格式"""
        url_lower = url.lower()
        if url_lower.endswith((".yaml", ".yml")):
            return SourceFormat.CLASH
        if "clash" in url_lower:
            return SourceFormat.CLASH
        if "base64" in url_lower:
            return SourceFormat.BASE64
        if url_lower.endswith(".txt") or "nodes" in url_lower or "sub" in url_lower:
            return SourceFormat.TEXT
        if content_hint:
            if "proxies:" in content_hint[:500]:
                return SourceFormat.CLASH
        return SourceFormat.AUTO

    def _is_usable_url(self, url: str) -> bool:
        """检查 URL 是否可用"""
        if not url or len(url) > 2048:
            return False
        if url.startswith("data:") and len(url) > 10000:
            return False

        try:
            parsed = urlparse(url)
            host = (parsed.hostname or "").lower()

            if not host:
                return False

            # 拦截内网地址
            if host in _BLOCKED_HOSTS:
                return False
            if host.startswith(_BLOCKED_IP_PREFIXES):
                return False
            if host.endswith(".onion"):
                return False

            return True
        except Exception:
            return False

    def _name_from_url(self, url: str) -> str:
        """从 URL 生成名称"""
        try:
            parsed = urlparse(url)
            parts = parsed.path.strip("/").split("/")
            if parts:
                return parts[-1][:50]
        except Exception:
            pass
        return url[:50]
