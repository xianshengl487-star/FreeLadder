# path: freeladder/source_intel/source_validator.py
"""源验证器

验证候选源是否真的能解析出节点，而不是只保存链接。
"""

import httpx
from loguru import logger

from .models import SourceRecord


class SourceValidator:
    """源验证器"""

    def __init__(self, config=None):
        if config is None:
            from freeladder.core.config import get_config
            config = get_config().source_intel
        self._config = config

    def validate(self, source: SourceRecord) -> dict:
        """验证源能否解析出节点"""
        try:
            content = self.download_source(source)
            if not content:
                return {"valid": False, "node_count": 0, "protocol_stats": {},
                        "error": "下载失败或内容为空", "content_changed": False}

            nodes = self.parse_nodes(content)
            if not nodes:
                return {"valid": False, "node_count": 0, "protocol_stats": {},
                        "error": "无法解析出节点", "content_changed": False}

            node_count = len(nodes)
            if node_count < self._config.min_nodes_to_accept:
                return {"valid": False, "node_count": node_count, "protocol_stats": {},
                        "error": f"节点数不足（{node_count} < {self._config.min_nodes_to_accept}）",
                        "content_changed": False}

            protocol_stats = self.collect_protocol_stats(nodes)
            return {"valid": True, "node_count": node_count,
                    "protocol_stats": protocol_stats, "error": "",
                    "content_changed": True}
        except Exception as e:
            logger.debug(f"验证源失败 {source.url}: {e}")
            return {"valid": False, "node_count": 0, "protocol_stats": {},
                    "error": str(e)[:200], "content_changed": False}

    def download_source(self, source: SourceRecord) -> str:
        """下载源内容（带大小限制和超时）"""
        max_bytes = self._config.max_download_mb * 1024 * 1024
        timeout = self._config.request_timeout_seconds
        headers = {"User-Agent": self._config.user_agent}

        # 传递 ETag / Last-Modified
        if source.etag:
            headers["If-None-Match"] = source.etag
        if source.last_modified:
            headers["If-Modified-Since"] = source.last_modified

        try:
            with httpx.Client(timeout=timeout, follow_redirects=True) as client:
                resp = client.get(source.url, headers=headers)
                # 304 Not Modified
                if resp.status_code == 304:
                    return ""
                resp.raise_for_status()

                # 检查大小
                content_length = resp.headers.get("content-length")
                if content_length and int(content_length) > max_bytes:
                    logger.warning(f"源内容过大: {source.url} ({content_length} bytes)")
                    return ""

                content = resp.text
                if len(content.encode("utf-8")) > max_bytes:
                    logger.warning(f"源内容过大: {source.url}")
                    return ""

                return content
        except httpx.TimeoutException:
            logger.debug(f"验证源超时: {source.url}")
            return ""
        except httpx.HTTPStatusError as e:
            logger.debug(f"验证源 HTTP 错误 {e.response.status_code}: {source.url}")
            return ""
        except Exception as e:
            logger.debug(f"验证源失败 {source.url}: {e}")
            return ""

    def parse_nodes(self, content: str) -> list:
        """使用现有节点解析逻辑"""
        from freeladder.scraper.sources import (
            decode_subscription_content,
            extract_nodes_from_clash_yaml,
        )
        from freeladder.scraper.parser import parse_nodes_from_text

        stripped = content.strip()

        # 尝试 Clash YAML 解析
        if stripped.startswith('{') or stripped.startswith('proxies:') or 'proxies:' in stripped[:200]:
            try:
                import yaml
                yaml.safe_load(stripped)
                nodes = extract_nodes_from_clash_yaml(stripped)
                if nodes:
                    return nodes[:self._config.max_nodes_per_source]
            except Exception:
                pass

        # 解码内容
        decoded = decode_subscription_content(content)
        if not decoded:
            return []

        # 解码后也尝试 Clash YAML
        decoded_stripped = decoded.strip()
        if decoded_stripped.startswith('{') or 'proxies:' in decoded_stripped[:200]:
            try:
                import yaml
                yaml.safe_load(decoded_stripped)
                nodes = extract_nodes_from_clash_yaml(decoded_stripped)
                if nodes:
                    return nodes[:self._config.max_nodes_per_source]
            except Exception:
                pass

        # 按行解析 URI
        nodes = parse_nodes_from_text(decoded)
        return nodes[:self._config.max_nodes_per_source]

    def collect_protocol_stats(self, nodes: list) -> dict:
        """收集协议分布统计"""
        stats: dict[str, int] = {}
        for node in nodes:
            proto = node.protocol.value if hasattr(node, 'protocol') else "unknown"
            stats[proto] = stats.get(proto, 0) + 1
        return stats
