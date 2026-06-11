"""tests/test_node_key.py
验证高级协议不会因为同一个 server:port 被误去重。
"""
from freeladder.core.models import Node, Protocol


def test_advanced_node_key_uses_raw_uri_hash():
    n1 = Node(
        protocol=Protocol.VLESS,
        server="example.com",
        port=443,
        raw_uri="vless://uuid-1@example.com:443?security=tls#A",
    )
    n2 = Node(
        protocol=Protocol.VLESS,
        server="example.com",
        port=443,
        raw_uri="vless://uuid-2@example.com:443?security=tls#B",
    )

    assert n1.node_key != n2.node_key


def test_fragment_does_not_affect_node_key():
    n1 = Node(
        protocol=Protocol.VLESS,
        server="example.com",
        port=443,
        raw_uri="vless://uuid@example.com:443?security=tls#NameA",
    )
    n2 = Node(
        protocol=Protocol.VLESS,
        server="example.com",
        port=443,
        raw_uri="vless://uuid@example.com:443?security=tls#NameB",
    )

    assert n1.node_key == n2.node_key


def test_plain_ip_port_node_key():
    """1.2.3.4:8080 不含 :// ，应退回到 protocol://server:port"""
    n = Node(
        protocol=Protocol.HTTP,
        server="1.2.3.4",
        port=8080,
        raw_uri="1.2.3.4:8080",
    )

    assert n.node_key == "http://1.2.3.4:8080"


def test_node_without_raw_uri():
    """无 raw_uri 时退回到 protocol://server:port"""
    n = Node(
        protocol=Protocol.SOCKS5,
        server="10.0.0.1",
        port=1080,
    )

    assert n.node_key == "socks5://10.0.0.1:1080"
