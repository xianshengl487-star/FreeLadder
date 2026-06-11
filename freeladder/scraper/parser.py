# path: freeladder/scraper/parser.py
"""节点 URI 解析模块

支持解析:
- IP:port (默认 HTTP)
- http:// / https://
- socks5://
- vmess:// (base64 JSON)
- vless://
- trojan://
- ss:// (base64)
- ssr:// (base64)
- hysteria:// / hysteria2://
- tuic://
"""

import base64
import json
import re
from typing import Optional
from urllib.parse import urlparse, parse_qs, unquote

from loguru import logger

from freeladder.core.models import Node, Protocol


def _safe_base64_decode(data: str) -> str:
    """安全 base64 解码"""
    # 补齐 padding
    missing = len(data) % 4
    if missing:
        data += '=' * (4 - missing)
    try:
        return base64.b64decode(data).decode("utf-8", errors="ignore")
    except Exception:
        return ""


def _extract_clash_proxy(protocol: Protocol, server: str, port: int, name: str, **kwargs) -> dict:
    """尝试构建 Clash/Mihomo 代理字典"""
    proxy = {"name": name, "type": protocol.value, "server": server, "port": port}

    if protocol == Protocol.HTTP:
        proxy["type"] = "http"
        if kwargs.get("username"):
            proxy["username"] = kwargs["username"]
            proxy["password"] = kwargs["password"]
        proxy["tls"] = kwargs.get("tls", False)

    elif protocol == Protocol.SOCKS5:
        proxy["type"] = "socks5"
        if kwargs.get("username"):
            proxy["username"] = kwargs["username"]
            proxy["password"] = kwargs["password"]

    elif protocol == Protocol.SS:
        proxy["type"] = "ss"
        if kwargs.get("cipher"):
            proxy["cipher"] = kwargs["cipher"]
        if kwargs.get("password"):
            proxy["password"] = kwargs["password"]

    elif protocol == Protocol.VMESS:
        proxy["type"] = "vmess"
        # vmess 的完整参数从 raw_uri 解析后传入
        for key in ["uuid", "alterId", "cipher", "tls", "network", "ws-path",
                     "ws-headers", "servername", "skip-cert-verify", "udp"]:
            if kwargs.get(key) is not None:
                proxy[key] = kwargs[key]

    elif protocol == Protocol.VLESS:
        proxy["type"] = "vless"
        for key in ["uuid", "tls", "network", "ws-path", "ws-headers",
                     "servername", "skip-cert-verify", "flow", "udp"]:
            if kwargs.get(key) is not None:
                proxy[key] = kwargs[key]

    elif protocol == Protocol.TROJAN:
        proxy["type"] = "trojan"
        if kwargs.get("password"):
            proxy["password"] = kwargs["password"]
        for key in ["sni", "skip-cert-verify", "udp", "network", "ws-path"]:
            if kwargs.get(key) is not None:
                proxy[key] = kwargs[key]

    elif protocol in (Protocol.HYSTERIA, Protocol.HYSTERIA2):
        proxy["type"] = "hysteria2" if protocol == Protocol.HYSTERIA2 else "hysteria"
        for key in ["password", "obfs", "obfs-password", "sni",
                     "skip-cert-verify", "up", "down"]:
            if kwargs.get(key) is not None:
                proxy[key] = kwargs[key]

    elif protocol == Protocol.TUIC:
        proxy["type"] = "tuic"
        for key in ["uuid", "password", "alpn", "sni",
                     "skip-cert-verify", "udp-relay"]:
            if kwargs.get(key) is not None:
                proxy[key] = kwargs[key]

    return proxy


def parse_vmess(uri: str) -> Optional[Node]:
    """解析 vmess:// URI"""
    try:
        # vmess:// 后面是 base64 编码的 JSON
        raw = uri[len("vmess://"):]
        decoded = _safe_base64_decode(raw)
        if not decoded:
            return None

        data = json.loads(decoded)

        server = data.get("add", data.get("host", ""))
        port = int(data.get("port", 0))
        name = data.get("ps", "")
        if not server or port <= 0:
            return None

        if not name:
            name = f"VMess-{server}:{port}"

        # 构建 vmess 参数
        kwargs = {
            "uuid": data.get("id", ""),
            "alterId": int(data.get("aid", 0)),
            "cipher": data.get("scy", data.get("cipher", "auto")),
            "tls": data.get("tls", "") == "tls",
            "network": data.get("net", "tcp"),
            "ws-path": data.get("path", ""),
            "servername": data.get("sni", data.get("host", "")),
            "skip-cert-verify": data.get("tls") == "tls",
            "udp": True,
        }

        # WebSocket headers
        host = data.get("host", "")
        if host and data.get("net") == "ws":
            kwargs["ws-headers"] = {"Host": host}

        clash_proxy = _extract_clash_proxy(Protocol.VMESS, server, port, name, **kwargs)

        return Node(
            protocol=Protocol.VMESS,
            server=server,
            port=port,
            name=name,
            raw_uri=uri,
            clash_proxy=clash_proxy,
        )
    except Exception as e:
        logger.debug(f"vmess 解析失败: {e}")
        return None


def parse_ss(uri: str) -> Optional[Node]:
    """解析 ss:// URI (Shadowsocks)"""
    try:
        raw = uri[len("ss://"):]

        # 格式: base64(method:password)@server:port#name
        # 或: base64(method:password@server:port)#name
        # 或: base64(json)

        # 先检查是否有 @ 分隔符
        if '@' in raw:
            # 分离 #name
            if '#' in raw:
                main_part, name = raw.rsplit('#', 1)
                name = unquote(name)
            else:
                main_part = raw
                name = ""

            # 找到 @ 位置（可能在 base64 编码内）
            # 尝试解码后找 @
            # base64 部分 + @ + server:port
            at_pos = main_part.find('@')
            if at_pos == -1:
                # 尝试 base64 解码
                decoded = _safe_base64_decode(main_part)
                if '@' in decoded:
                    method_pass, server_port = decoded.rsplit('@', 1)
                else:
                    return None
            else:
                encoded_part = main_part[:at_pos]
                server_port = main_part[at_pos+1:]
                method_pass = _safe_base64_decode(encoded_part)

            if ':' in method_pass:
                method, password = method_pass.split(':', 1)
            else:
                method = method_pass
                password = ""

            server, port_str = server_port.rsplit(':', 1)
            port = int(port_str)

            if not name:
                name = f"SS-{server}:{port}"

            clash_proxy = _extract_clash_proxy(
                Protocol.SS, server, port, name,
                cipher=method, password=password
            )

            return Node(
                protocol=Protocol.SS,
                server=server,
                port=port,
                name=name,
                raw_uri=uri,
                clash_proxy=clash_proxy,
            )
        else:
            # 尝试 base64 解码整个内容
            decoded = _safe_base64_decode(raw)
            if decoded:
                return parse_ss(f"ss://{decoded}")
            return None
    except Exception as e:
        logger.debug(f"ss 解析失败: {e}")
        return None


def parse_ssr(uri: str) -> Optional[Node]:
    """解析 ssr:// URI (ShadowsocksR)"""
    try:
        raw = uri[len("ssr://"):]
        decoded = _safe_base64_decode(raw)
        if not decoded:
            return None

        # 格式: server:port:protocol:method:obfs:base64pass/?params
        parts = decoded.split(':')
        if len(parts) < 6:
            return None

        server = parts[0]
        port = int(parts[1])
        # parts[2] = protocol, parts[3] = method, parts[4] = obfs
        password_b64 = parts[5]
        password = _safe_base64_decode(password_b64)

        name = f"SSR-{server}:{port}"

        clash_proxy = {
            "name": name,
            "type": "ssr",
            "server": server,
            "port": port,
            "cipher": parts[3],
            "password": password,
            "protocol": parts[2],
            "protocol-param": "",
            "obfs": parts[4],
            "obfs-param": "",
        }

        return Node(
            protocol=Protocol.SSR,
            server=server,
            port=port,
            name=name,
            raw_uri=uri,
            clash_proxy=clash_proxy,
        )
    except Exception as e:
        logger.debug(f"ssr 解析失败: {e}")
        return None


def parse_vless(uri: str) -> Optional[Node]:
    """解析 vless:// URI"""
    try:
        parsed = urlparse(uri)
        server = parsed.hostname
        port = parsed.port
        if not server or not port:
            return None

        # uuid@server:port?params#name
        uuid = parsed.username or ""
        name = unquote(parsed.fragment) if parsed.fragment else ""

        if not name:
            name = f"VLESS-{server}:{port}"

        params = parse_qs(parsed.query)

        kwargs = {
            "uuid": uuid,
            "tls": params.get("security", [""])[0] == "tls",
            "network": params.get("type", ["tcp"])[0],
            "servername": params.get("sni", [""])[0],
            "skip-cert-verify": params.get("allowInsecure", ["0"])[0] == "1",
            "flow": params.get("flow", [""])[0],
            "udp": True,
        }

        # WebSocket
        if params.get("type", [""])[0] == "ws":
            kwargs["ws-path"] = params.get("path", [""])[0]
            host_header = params.get("host", [""])[0]
            if host_header:
                kwargs["ws-headers"] = {"Host": host_header}

        clash_proxy = _extract_clash_proxy(Protocol.VLESS, server, port, name, **kwargs)

        return Node(
            protocol=Protocol.VLESS,
            server=server,
            port=port,
            name=name,
            raw_uri=uri,
            clash_proxy=clash_proxy,
        )
    except Exception as e:
        logger.debug(f"vless 解析失败: {e}")
        return None


def parse_trojan(uri: str) -> Optional[Node]:
    """解析 trojan:// URI"""
    try:
        parsed = urlparse(uri)
        server = parsed.hostname
        port = parsed.port
        if not server or not port:
            return None

        password = unquote(parsed.username) if parsed.username else ""
        name = unquote(parsed.fragment) if parsed.fragment else ""

        if not name:
            name = f"Trojan-{server}:{port}"

        params = parse_qs(parsed.query)

        kwargs = {
            "password": password,
            "sni": params.get("sni", [""])[0],
            "skip-cert-verify": params.get("allowInsecure", ["0"])[0] == "1",
            "udp": True,
        }

        clash_proxy = _extract_clash_proxy(Protocol.TROJAN, server, port, name, **kwargs)

        return Node(
            protocol=Protocol.TROJAN,
            server=server,
            port=port,
            name=name,
            raw_uri=uri,
            clash_proxy=clash_proxy,
        )
    except Exception as e:
        logger.debug(f"trojan 解析失败: {e}")
        return None


def parse_hysteria(uri: str, version: int = 1) -> Optional[Node]:
    """解析 hysteria:// / hysteria2:// URI"""
    try:
        parsed = urlparse(uri)
        server = parsed.hostname
        port = parsed.port
        if not server or not port:
            return None

        password = unquote(parsed.username) if parsed.username else ""
        name = unquote(parsed.fragment) if parsed.fragment else ""
        proto = Protocol.HYSTERIA2 if version == 2 else Protocol.HYSTERIA

        if not name:
            tag = "Hysteria2" if version == 2 else "Hysteria"
            name = f"{tag}-{server}:{port}"

        params = parse_qs(parsed.query)

        kwargs = {
            "password": password,
            "obfs": params.get("obfs", [""])[0],
            "obfs-password": params.get("obfs-password", [""])[0],
            "sni": params.get("sni", [""])[0],
            "skip-cert-verify": params.get("insecure", ["0"])[0] == "1",
        }

        clash_proxy = _extract_clash_proxy(proto, server, port, name, **kwargs)

        return Node(
            protocol=proto,
            server=server,
            port=port,
            name=name,
            raw_uri=uri,
            clash_proxy=clash_proxy,
        )
    except Exception as e:
        logger.debug(f"hysteria{version} 解析失败: {e}")
        return None


def parse_tuic(uri: str) -> Optional[Node]:
    """解析 tuic:// URI"""
    try:
        parsed = urlparse(uri)
        server = parsed.hostname
        port = parsed.port
        if not server or not port:
            return None

        # tuic://uuid:password@server:port?params#name
        uuid = unquote(parsed.username) if parsed.username else ""
        password = unquote(parsed.password) if parsed.password else ""
        name = unquote(parsed.fragment) if parsed.fragment else ""

        if not name:
            name = f"TUIC-{server}:{port}"

        params = parse_qs(parsed.query)

        kwargs = {
            "uuid": uuid,
            "password": password,
            "alpn": params.get("alpn", ["h3"])[0],
            "sni": params.get("sni", [""])[0],
            "skip-cert-verify": params.get("allowInsecure", ["0"])[0] == "1",
            "udp-relay": params.get("udp_relay_mode", ["native"])[0] == "native",
        }

        clash_proxy = _extract_clash_proxy(Protocol.TUIC, server, port, name, **kwargs)

        return Node(
            protocol=Protocol.TUIC,
            server=server,
            port=port,
            name=name,
            raw_uri=uri,
            clash_proxy=clash_proxy,
        )
    except Exception as e:
        logger.debug(f"tuic 解析失败: {e}")
        return None


def parse_http_proxy(uri: str) -> Optional[Node]:
    """解析 http:// / https:// / socks5:// URI"""
    try:
        parsed = urlparse(uri)
        protocol_str = parsed.scheme.lower()
        server = parsed.hostname
        port = parsed.port
        if not server or not port:
            return None

        if protocol_str == "socks5":
            protocol = Protocol.SOCKS5
        elif protocol_str == "https":
            protocol = Protocol.HTTPS
        else:
            protocol = Protocol.HTTP

        name = unquote(parsed.fragment) if parsed.fragment else ""
        if not name:
            name = f"{protocol_str.upper()}-{server}:{port}"

        kwargs = {}
        if parsed.username:
            kwargs["username"] = unquote(parsed.username)
        if parsed.password:
            kwargs["password"] = unquote(parsed.password)
        if protocol == Protocol.HTTPS:
            kwargs["tls"] = True

        clash_proxy = _extract_clash_proxy(protocol, server, port, name, **kwargs)

        return Node(
            protocol=protocol,
            server=server,
            port=port,
            name=name,
            raw_uri=uri,
            clash_proxy=clash_proxy,
        )
    except Exception as e:
        logger.debug(f"HTTP/SOCKS5 解析失败: {e}")
        return None


def parse_ip_port(text: str) -> Optional[Node]:
    """解析 IP:port 格式（默认 HTTP）"""
    text = text.strip()
    match = re.match(r'^(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}):(\d{1,5})$', text)
    if not match:
        return None

    server = match.group(1)
    port = int(match.group(2))

    if port <= 0 or port > 65535:
        return None

    name = f"HTTP-{server}:{port}"
    clash_proxy = _extract_clash_proxy(Protocol.HTTP, server, port, name)

    return Node(
        protocol=Protocol.HTTP,
        server=server,
        port=port,
        name=name,
        raw_uri=text,
        clash_proxy=clash_proxy,
    )


def parse_uri(uri: str) -> Optional[Node]:
    """解析单个 URI，自动识别协议"""
    uri = uri.strip()
    if not uri:
        return None

    # 按协议前缀分发
    lower = uri.lower()

    if lower.startswith("vmess://"):
        return parse_vmess(uri)
    elif lower.startswith("vless://"):
        return parse_vless(uri)
    elif lower.startswith("trojan://"):
        return parse_trojan(uri)
    elif lower.startswith("ss://"):
        return parse_ss(uri)
    elif lower.startswith("ssr://"):
        return parse_ssr(uri)
    elif lower.startswith("hysteria2://") or lower.startswith("hy2://"):
        return parse_hysteria(uri, version=2)
    elif lower.startswith("hysteria://"):
        return parse_hysteria(uri, version=1)
    elif lower.startswith("tuic://"):
        return parse_tuic(uri)
    elif lower.startswith("http://") or lower.startswith("https://") or lower.startswith("socks5://"):
        return parse_http_proxy(uri)
    else:
        # 尝试 IP:port
        return parse_ip_port(uri)


def parse_nodes_from_text(text: str) -> list[Node]:
    """从文本中提取并解析所有节点 URI"""
    nodes = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        node = parse_uri(line)
        if node:
            nodes.append(node)
    return nodes
