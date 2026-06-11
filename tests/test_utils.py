# path: tests/test_utils.py
"""测试通用工具函数"""

import pytest

from freeladder.core.utils import (
    is_valid_ip,
    is_valid_port,
    parse_server_port,
    mask_secret,
    make_unique_proxy_names,
)


class TestIsValidIp:

    @pytest.mark.parametrize("ip", [
        "1.2.3.4",
        "0.0.0.0",
        "255.255.255.255",
        "192.168.1.1",
    ])
    def test_valid_ips(self, ip):
        assert is_valid_ip(ip) is True

    @pytest.mark.parametrize("ip", [
        "256.1.1.1",
        "1.2.3",
        "abc.def.ghi.jkl",
        "",
        "1.2.3.4.5",
    ])
    def test_invalid_ips(self, ip):
        assert is_valid_ip(ip) is False


class TestIsValidPort:

    @pytest.mark.parametrize("port", [1, 80, 443, 8080, 65535])
    def test_valid_ports(self, port):
        assert is_valid_port(port) is True

    @pytest.mark.parametrize("port", [0, -1, 65536, 100000])
    def test_invalid_ports(self, port):
        assert is_valid_port(port) is False


class TestParseServerPort:

    def test_basic(self):
        host, port = parse_server_port("1.2.3.4:8080")
        assert host == "1.2.3.4"
        assert port == 8080

    def test_ipv6(self):
        host, port = parse_server_port("[::1]:8080")
        assert host == "::1"
        assert port == 8080

    def test_ipv6_no_port(self):
        host, port = parse_server_port("[::1]")
        assert host == "::1"
        assert port == 0

    def test_no_port(self):
        host, port = parse_server_port("1.2.3.4")
        assert host == "1.2.3.4"
        assert port == 0

    def test_multiple_colons(self):
        host, port = parse_server_port("host:name:80")
        assert host == "host:name"
        assert port == 80


class TestMaskSecret:

    def test_long_secret(self):
        result = mask_secret("abcdefghijklmnop")
        assert result.startswith("abcd")
        assert result.endswith("mnop")
        assert "****" in result

    def test_short_secret(self):
        result = mask_secret("short")
        assert result == "****"

    def test_empty_secret(self):
        result = mask_secret("")
        assert result == "****"

    def test_exactly_8_chars(self):
        result = mask_secret("12345678")
        assert result == "1234****5678"


class TestMakeUniqueProxyNames:

    def test_no_duplicates(self):
        proxies = [
            {"name": "Node A", "type": "http"},
            {"name": "Node B", "type": "http"},
        ]
        result = make_unique_proxy_names(proxies)
        assert result[0]["name"] == "Node A"
        assert result[1]["name"] == "Node B"

    def test_duplicate_names(self):
        proxies = [
            {"name": "same", "type": "http"},
            {"name": "same", "type": "http"},
        ]
        result = make_unique_proxy_names(proxies)
        assert result[0]["name"] == "same"
        assert result[1]["name"] == "same-2"

    def test_empty_name_gets_default(self):
        proxies = [
            {"name": "", "type": "http"},
        ]
        result = make_unique_proxy_names(proxies)
        assert result[0]["name"] == "Node-1"

    def test_none_name_gets_default(self):
        proxies = [
            {"type": "http"},
        ]
        result = make_unique_proxy_names(proxies)
        assert result[0]["name"] == "Node-1"

    def test_does_not_mutate_original(self):
        proxies = [
            {"name": "same", "type": "http"},
            {"name": "same", "type": "http"},
        ]
        original_names = [p["name"] for p in proxies]
        make_unique_proxy_names(proxies)
        assert [p["name"] for p in proxies] == original_names

    def test_triple_duplicates(self):
        proxies = [
            {"name": "dup", "type": "http"},
            {"name": "dup", "type": "http"},
            {"name": "dup", "type": "http"},
        ]
        result = make_unique_proxy_names(proxies)
        assert result[0]["name"] == "dup"
        assert result[1]["name"] == "dup-2"
        assert result[2]["name"] == "dup-3"
