# path: tests/test_models.py
"""数据模型测试"""

import pytest

from freeladder.core.models import Node, Protocol, TestResult, ExportOptions


class TestProtocol:
    def test_all_protocols(self):
        protocols = list(Protocol)
        assert len(protocols) == 12
        assert Protocol.HTTP in protocols
        assert Protocol.HTTPS in protocols
        assert Protocol.SOCKS5 in protocols
        assert Protocol.VMESS in protocols
        assert Protocol.VLESS in protocols
        assert Protocol.TROJAN in protocols
        assert Protocol.SS in protocols
        assert Protocol.SSR in protocols
        assert Protocol.HYSTERIA in protocols
        assert Protocol.HYSTERIA2 in protocols
        assert Protocol.TUIC in protocols
        assert Protocol.UNKNOWN in protocols

    def test_protocol_values(self):
        assert Protocol.HTTP.value == "http"
        assert Protocol.SOCKS5.value == "socks5"
        assert Protocol.VMESS.value == "vmess"
        assert Protocol.VLESS.value == "vless"
        assert Protocol.TROJAN.value == "trojan"
        assert Protocol.SS.value == "ss"


class TestNode:
    def test_create_minimal(self):
        node = Node(
            protocol=Protocol.VMESS,
            server="10.0.0.1",
            port=443,
        )
        assert node.protocol == Protocol.VMESS
        assert node.server == "10.0.0.1"
        assert node.port == 443
        assert node.node_key.startswith("vmess")

    def test_create_full(self):
        node = Node(
            protocol=Protocol.VMESS,
            server="10.0.0.1",
            port=443,
            name="test-vmess",
            raw_uri="vmess://test",
            clash_proxy={"name": "test", "type": "vmess"},
            country="US",
            alive=True,
            latency=50,
            avg_latency=45.5,
            score=85.0,
            signal="good",
            test_mode="TCP",
            fail_count=0,
            success_count=5,
            last_error="",
            source="builtin",
            created_at="2025-01-01 00:00:00",
            updated_at="2025-01-01 00:00:00",
            last_checked="2025-01-01 00:00:00",
        )
        assert node.name == "test-vmess"
        assert node.alive is True
        assert node.latency == 50
        assert node.score == 85.0

    def test_node_defaults(self):
        node = Node(
            protocol=Protocol.VMESS,
            server="10.0.0.1",
            port=443,
        )
        assert node.alive is False
        assert node.latency is None
        assert node.score == 0.0
        assert node.fail_count == 0
        assert node.success_count == 0
        assert node.country == ""
        assert node.name == ""


class TestTestResult:
    def test_create(self):
        result = TestResult(
            node_id=1,
            alive=True,
            latency=50,
            test_mode="TCP",
            tested_at="2025-01-01 00:00:00",
        )
        assert result.node_id == 1
        assert result.alive is True
        assert result.latency == 50

    def test_create_failed(self):
        result = TestResult(
            node_id=1,
            alive=False,
            latency=None,
            test_mode="TCP",
            tested_at="2025-01-01 00:00:00",
            error="Connection refused",
        )
        assert result.alive is False
        assert result.error == "Connection refused"


class TestExportOptions:
    def test_defaults(self):
        opts = ExportOptions()
        assert opts.alive_only is True
        assert opts.min_score == 0.0
        assert opts.protocols == []
        assert opts.max_nodes == 500

    def test_custom(self):
        opts = ExportOptions(
            alive_only=False,
            min_score=50,
            max_nodes=100,
            protocols=["vmess", "vless"],
        )
        assert opts.alive_only is False
        assert opts.min_score == 50
        assert opts.max_nodes == 100
        assert opts.protocols == ["vmess", "vless"]
