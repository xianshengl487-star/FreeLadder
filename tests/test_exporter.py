# path: tests/test_exporter.py
"""测试导出模块 (Clash YAML + Base64 订阅)"""

import pytest
from unittest.mock import patch, MagicMock

from freeladder.core.models import Node, Protocol, ExportOptions
from freeladder.core.dedup import deduplicate_nodes
from freeladder.exporter.clash_exporter import (
    _is_valid_proxy,
    _build_clash_config,
    get_clash_yaml_string,
)
from freeladder.exporter.subscription_exporter import get_subscription_string
from tests.conftest import make_node


# ──────────────────── _is_valid_proxy ────────────────────

class TestIsValidProxy:

    def test_valid_proxy(self):
        assert _is_valid_proxy({"name": "test", "type": "http", "server": "1.2.3.4", "port": 80}) is True

    def test_missing_name(self):
        assert _is_valid_proxy({"type": "http", "server": "1.2.3.4", "port": 80}) is False

    def test_missing_type(self):
        assert _is_valid_proxy({"name": "test", "server": "1.2.3.4", "port": 80}) is False

    def test_missing_server(self):
        assert _is_valid_proxy({"name": "test", "type": "http", "port": 80}) is False

    def test_port_zero(self):
        assert _is_valid_proxy({"name": "test", "type": "http", "server": "1.2.3.4", "port": 0}) is False

    def test_port_negative(self):
        assert _is_valid_proxy({"name": "test", "type": "http", "server": "1.2.3.4", "port": -1}) is False

    def test_port_too_large(self):
        assert _is_valid_proxy({"name": "test", "type": "http", "server": "1.2.3.4", "port": 99999}) is False

    def test_not_dict(self):
        assert _is_valid_proxy("not a dict") is False

    def test_port_not_int(self):
        assert _is_valid_proxy({"name": "test", "type": "http", "server": "1.2.3.4", "port": "abc"}) is False


# ──────────────────── _build_clash_config ────────────────────

class TestBuildClashConfig:

    def test_empty_nodes(self):
        config = _build_clash_config([])
        assert config["proxies"] == []
        assert config["rules"] == ["MATCH,DIRECT"]

    def test_valid_nodes(self):
        nodes = [
            make_node(
                protocol=Protocol.HTTP, server="1.2.3.4", port=80,
                clash_proxy={"name": "Node1", "type": "http", "server": "1.2.3.4", "port": 80},
            ),
            make_node(
                protocol=Protocol.SOCKS5, server="5.6.7.8", port=1080,
                clash_proxy={"name": "Node2", "type": "socks5", "server": "5.6.7.8", "port": 1080},
            ),
        ]
        config = _build_clash_config(nodes)
        assert len(config["proxies"]) == 2
        assert len(config["proxy-groups"]) == 2
        assert config["proxy-groups"][0]["name"] == "Auto"
        assert config["proxy-groups"][1]["name"] == "Proxy"

    def test_filters_invalid_proxies(self):
        nodes = [
            make_node(protocol=Protocol.HTTP, server="1.2.3.4", port=80,
                      clash_proxy={"name": "good", "type": "http", "server": "1.2.3.4", "port": 80}),
            make_node(protocol=Protocol.HTTP, server="1.2.3.4", port=80,
                      clash_proxy={"name": "", "type": "http", "server": "1.2.3.4", "port": 80}),
        ]
        config = _build_clash_config(nodes)
        assert len(config["proxies"]) == 1

    def test_unique_names(self):
        nodes = [
            make_node(protocol=Protocol.HTTP, server="1.2.3.4", port=80,
                      clash_proxy={"name": "same", "type": "http", "server": "1.2.3.4", "port": 80}),
            make_node(protocol=Protocol.HTTP, server="1.2.3.4", port=81,
                      clash_proxy={"name": "same", "type": "http", "server": "1.2.3.4", "port": 81}),
        ]
        config = _build_clash_config(nodes)
        names = [p["name"] for p in config["proxies"]]
        assert len(names) == len(set(names))

    def test_config_structure(self):
        config = _build_clash_config([])
        assert "port" in config
        assert "socks-port" in config
        assert "allow-lan" in config
        assert "mode" in config
        assert "log-level" in config


# ──────────────────── get_clash_yaml_string ────────────────────

class TestGetClashYamlString:

    def test_returns_string(self):
        import yaml
        nodes = [
            make_node(protocol=Protocol.HTTP, server="1.2.3.4", port=80,
                      clash_proxy={"name": "test", "type": "http", "server": "1.2.3.4", "port": 80}),
        ]
        result = get_clash_yaml_string(nodes)
        assert isinstance(result, str)
        data = yaml.safe_load(result)
        assert "proxies" in data

    def test_empty_nodes(self):
        result = get_clash_yaml_string([])
        import yaml
        data = yaml.safe_load(result)
        assert data["proxies"] == []


# ──────────────────── get_subscription_string ────────────────────

class TestGetSubscriptionString:

    def test_encodes_uris(self):
        import base64
        nodes = [
            make_node(protocol=Protocol.HTTP, server="1.2.3.4", port=80, raw_uri="http://1.2.3.4:80"),
            make_node(protocol=Protocol.SOCKS5, server="5.6.7.8", port=1080, raw_uri="socks5://5.6.7.8:1080"),
        ]
        result = get_subscription_string(nodes)
        decoded = base64.b64decode(result).decode("utf-8")
        assert "http://1.2.3.4:80" in decoded
        assert "socks5://5.6.7.8:1080" in decoded

    def test_skips_nodes_without_raw_uri(self):
        import base64
        nodes = [
            make_node(protocol=Protocol.HTTP, server="1.2.3.4", port=80, raw_uri=""),
            make_node(protocol=Protocol.HTTP, server="5.6.7.8", port=80, raw_uri="http://5.6.7.8:80"),
        ]
        result = get_subscription_string(nodes)
        decoded = base64.b64decode(result).decode("utf-8")
        assert "http://5.6.7.8:80" in decoded
        assert "1.2.3.4" not in decoded

    def test_empty_nodes(self):
        result = get_subscription_string([])
        import base64
        decoded = base64.b64decode(result).decode("utf-8")
        assert decoded == ""
