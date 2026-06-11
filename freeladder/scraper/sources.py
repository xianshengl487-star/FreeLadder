# path: freeladder/scraper/sources.py
"""订阅源管理模块"""

import base64
from typing import Optional

from loguru import logger

from freeladder.core.config import get_config


def load_sources() -> list[str]:
    """从配置中加载订阅源 URL 列表"""
    config = get_config()
    sources = config.scraper.sources
    if not sources:
        logger.warning("未配置任何订阅源，请在 config.yaml 的 scraper.sources 中添加")
    else:
        logger.info(f"已加载 {len(sources)} 个订阅源")
    return sources


def decode_subscription_content(content: str) -> str:
    """解码订阅内容（自动检测 base64）

    订阅源通常是 base64 编码的文本，包含节点 URI，每行一个。
    有些源直接返回明文。
    """
    # 先尝试去掉空白
    stripped = content.strip()

    # 检查是否是 base64
    # 简单启发式：如果内容只包含 base64 字符且长度合理
    import re
    b64_pattern = re.compile(r'^[A-Za-z0-9+/=\s]+$')
    if b64_pattern.match(stripped) and len(stripped) > 20:
        decoded = _safe_b64_decode(stripped)
        if decoded and any(proto in decoded.lower() for proto in
                          ['vmess://', 'vless://', 'trojan://', 'ss://',
                           'ssr://', 'hysteria', 'tuic://', 'http://',
                           'socks5://']):
            logger.debug("检测到 base64 编码订阅")
            return decoded

    # 可能是多行 base64（每行一个 URI，整体再 base64）
    lines = stripped.splitlines()
    if len(lines) == 1 and _looks_like_base64(stripped):
        decoded = _safe_b64_decode(stripped)
        if decoded:
            return decoded

    # 直接返回明文
    return stripped


def _looks_like_base64(text: str) -> bool:
    """判断文本是否像 base64"""
    import re
    # 去掉换行和空格后检查
    cleaned = text.replace('\n', '').replace('\r', '').replace(' ', '')
    return bool(re.match(r'^[A-Za-z0-9+/]+={0,2}$', cleaned))


def _safe_b64_decode(data: str) -> str:
    """安全 base64 解码"""
    cleaned = data.replace('\n', '').replace('\r', '').replace(' ', '')
    # 补齐 padding
    missing = len(cleaned) % 4
    if missing:
        cleaned += '=' * (4 - missing)
    try:
        result = base64.b64decode(cleaned)
        # 尝试多种编码
        for encoding in ['utf-8', 'gbk', 'gb2312', 'latin-1']:
            try:
                return result.decode(encoding)
            except (UnicodeDecodeError, ValueError):
                continue
        return result.decode('utf-8', errors='ignore')
    except Exception:
        return ""


def extract_uris_from_yaml(content: str) -> list[str]:
    """从 YAML 格式订阅中提取节点 URI"""
    import yaml
    uris = []
    try:
        data = yaml.safe_load(content)
        if isinstance(data, dict):
            # Clash 格式: proxies 列表
            proxies = data.get("proxies", [])
            if isinstance(proxies, list):
                for p in proxies:
                    if isinstance(p, dict):
                        # 构建简单 URI
                        proto = p.get("type", "")
                        server = p.get("server", "")
                        port = p.get("port", 0)
                        if server and port:
                            uris.append(f"{proto}://{server}:{port}")
        elif isinstance(data, list):
            # 列表格式
            for item in data:
                if isinstance(item, str):
                    uris.append(item)
                elif isinstance(item, dict):
                    proto = item.get("type", item.get("protocol", ""))
                    server = item.get("server", item.get("host", ""))
                    port = item.get("port", 0)
                    if server and port:
                        uris.append(f"{proto}://{server}:{port}")
    except yaml.YAMLError:
        pass
    return uris
