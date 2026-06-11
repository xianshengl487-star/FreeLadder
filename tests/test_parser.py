# path: tests/test_parser.py
"""测试节点 URI 解析模块"""

import base64
import json

import pytest

from freeladder.core.models import Protocol
from freeladder.scraper.parser import (
    parse_vmess,
    parse_ss,
    parse_ssr,
    parse_vless,
    parse_trojan,
    parse_hysteria,
    parse_tuic,
    parse_http_proxy,
    parse_ip_port,
    parse_uri,
    parse_nodes_from_text,
    _safe_base64_decode,
    _extract_clash_proxy,
)


# ──────────────────── helper ────────────────────

def _b64(s: str) -> str:
    return base64.b64encode(s.encode()).decode()


# ──────────────────── _safe_base64_decode ────────────────────

class TestSafeBase64Decode:

    def test_valid_utf8(self):
        assert _safe_base64_decode(_b64("hello world")) == "hello world"

    def test_empty_input(self):
        assert _safe_base64_decode("") == ""

    def test_invalid_data(self):
        assert _safe_base64_decode("!!!not-base64!!!") == ""

    def test_missing_padding(self):
        data = _b64("test").rstrip("=")
        assert _safe_base64_decode(data) == "test"


# ──────────────────── _extract_clash_proxy ────────────────────

class TestExtractClashProxy:

    def test_http_proxy(self):
        proxy = _extract_clash_proxy(Protocol.HTTP, "1.2.3.4", 80, "test",
                                     username="user", password="pass", tls=True)
        assert proxy["type"] == "http"
        assert proxy["username"] == "user"
        assert proxy["password"] == "pass"
        assert proxy["tls"] is True

    def test_socks5_proxy(self):
        proxy = _extract_clash_proxy(Protocol.SOCKS5, "1.2.3.4", 1080, "test",
                                     username="u", password="p")
        assert proxy["type"] == "socks5"
        assert proxy["username"] == "u"

    def test_ss_proxy(self):
        proxy = _extract_clash_proxy(Protocol.SS, "1.2.3.4", 8388, "test",
                                     cipher="aes-256-gcm", password="pass")
        assert proxy["type"] == "ss"
        assert proxy["cipher"] == "aes-256-gcm"

    def test_vmess_proxy(self):
        proxy = _extract_clash_proxy(Protocol.VMESS, "1.2.3.4", 443, "test",
                                     uuid="abc", alterId=0, cipher="auto",
                                     tls=True, network="ws", **{"ws-path": "/path"})
        assert proxy["type"] == "vmess"
        assert proxy["uuid"] == "abc"
        assert proxy["network"] == "ws"

    def test_vless_proxy(self):
        proxy = _extract_clash_proxy(Protocol.VLESS, "1.2.3.4", 443, "test",
                                     uuid="abc", tls=True, flow="xtls-rprx-vision")
        assert proxy["type"] == "vless"
        assert proxy["flow"] == "xtls-rprx-vision"

    def test_trojan_proxy(self):
        proxy = _extract_clash_proxy(Protocol.TROJAN, "1.2.3.4", 443, "test",
                                     password="pass", sni="sni.example.com")
        assert proxy["type"] == "trojan"
        assert proxy["password"] == "pass"

    def test_hysteria_proxy(self):
        proxy = _extract_clash_proxy(Protocol.HYSTERIA, "1.2.3.4", 443, "test",
                                     password="pass", obfs="salamander")
        assert proxy["type"] == "hysteria"

    def test_hysteria2_proxy(self):
        proxy = _extract_clash_proxy(Protocol.HYSTERIA2, "1.2.3.4", 443, "test",
                                     password="pass")
        assert proxy["type"] == "hysteria2"

    def test_tuic_proxy(self):
        proxy = _extract_clash_proxy(Protocol.TUIC, "1.2.3.4", 443, "test",
                                     uuid="abc", password="pass", alpn="h3")
        assert proxy["type"] == "tuic"
        assert proxy["alpn"] == "h3"


# ──────────────────── parse_vmess ────────────────────

class TestParseVmess:

    def test_basic_vmess(self):
        vmess_json = json.dumps({
            "add": "1.2.3.4",
            "port": "443",
            "id": "test-uuid",
            "aid": "0",
            "net": "tcp",
            "type": "none",
            "host": "",
            "path": "",
            "tls": "",
            "ps": "TestNode",
        })
        uri = f"vmess://{_b64(vmess_json)}"
        node = parse_vmess(uri)
        assert node is not None
        assert node.protocol == Protocol.VMESS
        assert node.server == "1.2.3.4"
        assert node.port == 443
        assert node.name == "TestNode"
        assert node.clash_proxy["uuid"] == "test-uuid"

    def test_vmess_with_ws(self):
        vmess_json = json.dumps({
            "add": "1.2.3.4",
            "port": "443",
            "id": "test-uuid",
            "aid": "0",
            "net": "ws",
            "type": "none",
            "host": "cdn.example.com",
            "path": "/ws",
            "tls": "tls",
            "ps": "WS-Node",
        })
        uri = f"vmess://{_b64(vmess_json)}"
        node = parse_vmess(uri)
        assert node is not None
        assert node.clash_proxy["network"] == "ws"
        assert node.clash_proxy["ws-path"] == "/ws"
        assert node.clash_proxy["ws-headers"] == {"Host": "cdn.example.com"}
        assert node.clash_proxy["tls"] is True

    def test_vmess_no_name(self):
        vmess_json = json.dumps({
            "add": "1.2.3.4",
            "port": "443",
            "id": "test-uuid",
            "aid": "0",
            "net": "tcp",
            "type": "none",
            "host": "",
            "path": "",
            "tls": "",
            "ps": "",
        })
        uri = f"vmess://{_b64(vmess_json)}"
        node = parse_vmess(uri)
        assert node is not None
        assert node.name == "VMess-1.2.3.4:443"

    def test_vmess_invalid_base64(self):
        assert parse_vmess("vmess://!!!invalid!!!") is None

    def test_vmess_empty_server(self):
        vmess_json = json.dumps({"add": "", "port": "443", "id": "x", "aid": "0"})
        uri = f"vmess://{_b64(vmess_json)}"
        assert parse_vmess(uri) is None

    def test_vmess_zero_port(self):
        vmess_json = json.dumps({"add": "1.2.3.4", "port": "0", "id": "x", "aid": "0"})
        uri = f"vmess://{_b64(vmess_json)}"
        assert parse_vmess(uri) is None


# ──────────────────── parse_ss ────────────────────

class TestParseSS:

    def test_ss_with_at_sign(self):
        # ss://base64(method:password)@server:port#name
        cred = _b64("aes-256-gcm:mypassword")
        uri = f"ss://{cred}@1.2.3.4:8388#SS-Node"
        node = parse_ss(uri)
        assert node is not None
        assert node.protocol == Protocol.SS
        assert node.server == "1.2.3.4"
        assert node.port == 8388
        assert node.name == "SS-Node"
        assert node.clash_proxy["cipher"] == "aes-256-gcm"
        assert node.clash_proxy["password"] == "mypassword"

    def test_ss_fully_encoded(self):
        # ss://base64(method:password@server:port)
        content = "aes-256-gcm:mypassword@1.2.3.4:8388"
        uri = f"ss://{_b64(content)}"
        node = parse_ss(uri)
        assert node is not None
        assert node.server == "1.2.3.4"

    def test_ss_no_name(self):
        cred = _b64("aes-256-gcm:pass")
        uri = f"ss://{cred}@1.2.3.4:8388"
        node = parse_ss(uri)
        assert node is not None
        assert node.name == "SS-1.2.3.4:8388"

    def test_ss_invalid(self):
        assert parse_ss("ss://!!!") is None


# ──────────────────── parse_ssr ────────────────────

class TestParseSSR:

    def test_basic_ssr(self):
        # ssr://base64(server:port:protocol:method:obfs:base64pass)
        password_b64 = _b64("mypassword")
        raw = f"1.2.3.4:8388:origin:aes-256-cfb:plain:{password_b64}"
        uri = f"ssr://{_b64(raw)}"
        node = parse_ssr(uri)
        assert node is not None
        assert node.protocol == Protocol.SSR
        assert node.server == "1.2.3.4"
        assert node.port == 8388
        assert node.clash_proxy["protocol"] == "origin"
        assert node.clash_proxy["cipher"] == "aes-256-cfb"
        assert node.clash_proxy["obfs"] == "plain"

    def test_ssr_too_few_parts(self):
        raw = "1.2.3.4:8388"
        uri = f"ssr://{_b64(raw)}"
        assert parse_ssr(uri) is None

    def test_ssr_invalid_base64(self):
        assert parse_ssr("ssr://!!!") is None


# ──────────────────── parse_vless ────────────────────

class TestParseVless:

    def test_basic_vless(self):
        uri = "vless://test-uuid@1.2.3.4:443?security=tls&sni=sni.example.com#VLESS-Node"
        node = parse_vless(uri)
        assert node is not None
        assert node.protocol == Protocol.VLESS
        assert node.server == "1.2.3.4"
        assert node.port == 443
        assert node.name == "VLESS-Node"
        assert node.clash_proxy["uuid"] == "test-uuid"
        assert node.clash_proxy["tls"] is True

    def test_vless_ws(self):
        uri = "vless://uuid@1.2.3.4:443?type=ws&path=/ws&host=cdn.example.com#WS"
        node = parse_vless(uri)
        assert node is not None
        assert node.clash_proxy["network"] == "ws"
        assert node.clash_proxy["ws-path"] == "/ws"
        assert node.clash_proxy["ws-headers"] == {"Host": "cdn.example.com"}

    def test_vless_no_name(self):
        uri = "vless://uuid@1.2.3.4:443"
        node = parse_vless(uri)
        assert node is not None
        assert node.name == "VLESS-1.2.3.4:443"

    def test_vless_no_server(self):
        uri = "vless://uuid@:443"
        assert parse_vless(uri) is None

    def test_vless_flow(self):
        uri = "vless://uuid@1.2.3.4:443?flow=xtls-rprx-vision#Flow"
        node = parse_vless(uri)
        assert node is not None
        assert node.clash_proxy["flow"] == "xtls-rprx-vision"


# ──────────────────── parse_trojan ────────────────────

class TestParseTrojan:

    def test_basic_trojan(self):
        uri = "trojan://mypassword@1.2.3.4:443?sni=sni.example.com#Trojan-Node"
        node = parse_trojan(uri)
        assert node is not None
        assert node.protocol == Protocol.TROJAN
        assert node.server == "1.2.3.4"
        assert node.port == 443
        assert node.clash_proxy["password"] == "mypassword"
        assert node.clash_proxy["sni"] == "sni.example.com"

    def test_trojan_no_name(self):
        uri = "trojan://pass@1.2.3.4:443"
        node = parse_trojan(uri)
        assert node is not None
        assert node.name == "Trojan-1.2.3.4:443"

    def test_trojan_no_server(self):
        uri = "trojan://pass@:443"
        assert parse_trojan(uri) is None


# ──────────────────── parse_hysteria ────────────────────

class TestParseHysteria:

    def test_hysteria1(self):
        uri = "hysteria://pass@1.2.3.4:443?obfs=salamander&obfs-password=obfspass&sni=sni.example.com#H1"
        node = parse_hysteria(uri, version=1)
        assert node is not None
        assert node.protocol == Protocol.HYSTERIA
        assert node.clash_proxy["obfs"] == "salamander"
        assert node.clash_proxy["obfs-password"] == "obfspass"

    def test_hysteria2(self):
        uri = "hysteria2://pass@1.2.3.4:443?sni=sni.example.com&insecure=1#H2"
        node = parse_hysteria(uri, version=2)
        assert node is not None
        assert node.protocol == Protocol.HYSTERIA2
        assert node.clash_proxy["skip-cert-verify"] is True

    def test_hysteria_no_name(self):
        uri = "hysteria2://pass@1.2.3.4:443"
        node = parse_hysteria(uri, version=2)
        assert node is not None
        assert node.name == "Hysteria2-1.2.3.4:443"


# ──────────────────── parse_tuic ────────────────────

class TestParseTUIC:

    def test_basic_tuic(self):
        uri = "tuic://uuid:password@1.2.3.4:443?alpn=h3&sni=sni.example.com#TUIC"
        node = parse_tuic(uri)
        assert node is not None
        assert node.protocol == Protocol.TUIC
        assert node.clash_proxy["uuid"] == "uuid"
        assert node.clash_proxy["password"] == "password"
        assert node.clash_proxy["alpn"] == "h3"

    def test_tuic_no_name(self):
        uri = "tuic://uuid:pass@1.2.3.4:443"
        node = parse_tuic(uri)
        assert node is not None
        assert node.name == "TUIC-1.2.3.4:443"


# ──────────────────── parse_http_proxy ────────────────────

class TestParseHttpProxy:

    def test_http(self):
        uri = "http://1.2.3.4:8080#HTTP-Proxy"
        node = parse_http_proxy(uri)
        assert node is not None
        assert node.protocol == Protocol.HTTP
        assert node.server == "1.2.3.4"
        assert node.port == 8080

    def test_https(self):
        uri = "https://1.2.3.4:443#HTTPS"
        node = parse_http_proxy(uri)
        assert node is not None
        assert node.protocol == Protocol.HTTPS
        # Note: _extract_clash_proxy doesn't have a Protocol.HTTPS branch,
        # so tls is not explicitly set in clash_proxy for HTTPS nodes.
        assert node.clash_proxy["type"] == "https"

    def test_socks5(self):
        uri = "socks5://user:pass@1.2.3.4:1080#Socks"
        node = parse_http_proxy(uri)
        assert node is not None
        assert node.protocol == Protocol.SOCKS5
        assert node.clash_proxy["username"] == "user"
        assert node.clash_proxy["password"] == "pass"

    def test_no_port(self):
        uri = "http://1.2.3.4"
        assert parse_http_proxy(uri) is None


# ──────────────────── parse_ip_port ────────────────────

class TestParseIpPort:

    def test_valid(self):
        node = parse_ip_port("1.2.3.4:8080")
        assert node is not None
        assert node.protocol == Protocol.HTTP
        assert node.server == "1.2.3.4"
        assert node.port == 8080

    def test_invalid_format(self):
        assert parse_ip_port("not-an-ip") is None

    def test_port_out_of_range(self):
        assert parse_ip_port("1.2.3.4:99999") is None

    def test_port_zero(self):
        assert parse_ip_port("1.2.3.4:0") is None


# ──────────────────── parse_uri (dispatcher) ────────────────────

class TestParseUri:

    def test_vmess_dispatch(self):
        vmess_json = json.dumps({"add": "1.2.3.4", "port": "443", "id": "x", "aid": "0"})
        uri = f"vmess://{_b64(vmess_json)}"
        assert parse_uri(uri).protocol == Protocol.VMESS

    def test_vless_dispatch(self):
        uri = "vless://uuid@1.2.3.4:443"
        assert parse_uri(uri).protocol == Protocol.VLESS

    def test_trojan_dispatch(self):
        uri = "trojan://pass@1.2.3.4:443"
        assert parse_uri(uri).protocol == Protocol.TROJAN

    def test_ss_dispatch(self):
        cred = _b64("aes-256-gcm:pass")
        uri = f"ss://{cred}@1.2.3.4:8388"
        assert parse_uri(uri).protocol == Protocol.SS

    def test_hysteria2_dispatch(self):
        uri = "hysteria2://pass@1.2.3.4:443"
        assert parse_uri(uri).protocol == Protocol.HYSTERIA2

    def test_hy2_alias(self):
        uri = "hy2://pass@1.2.3.4:443"
        assert parse_uri(uri).protocol == Protocol.HYSTERIA2

    def test_tuic_dispatch(self):
        uri = "tuic://uuid:pass@1.2.3.4:443"
        assert parse_uri(uri).protocol == Protocol.TUIC

    def test_http_dispatch(self):
        assert parse_uri("http://1.2.3.4:80").protocol == Protocol.HTTP

    def test_socks5_dispatch(self):
        assert parse_uri("socks5://1.2.3.4:1080").protocol == Protocol.SOCKS5

    def test_ip_port_fallback(self):
        assert parse_uri("1.2.3.4:8080").protocol == Protocol.HTTP

    def test_empty_string(self):
        assert parse_uri("") is None

    def test_whitespace_only(self):
        assert parse_uri("   ") is None


# ──────────────────── parse_nodes_from_text ────────────────────

class TestParseNodesFromText:

    def test_multi_line(self):
        text = "http://1.2.3.4:80\nsocks5://5.6.7.8:1080\n# comment\n\n1.1.1.1:443"
        nodes = parse_nodes_from_text(text)
        assert len(nodes) == 3

    def test_empty_text(self):
        assert parse_nodes_from_text("") == []

    def test_only_comments(self):
        assert parse_nodes_from_text("# line1\n# line2") == []
