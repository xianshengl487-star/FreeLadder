"""tests/test_dedup.py
验证去重保留信息更完整的节点。
"""
from freeladder.core.dedup import deduplicate_nodes
from freeladder.core.models import Node, Protocol


def test_dedup_keeps_different_advanced_nodes_same_server_port():
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

    result = deduplicate_nodes([n1, n2])

    assert len(result) == 2


def test_dedup_merges_same_plain_http_node():
    n1 = Node(protocol=Protocol.HTTP, server="1.2.3.4", port=8080, raw_uri="1.2.3.4:8080")
    n2 = Node(protocol=Protocol.HTTP, server="1.2.3.4", port=8080, raw_uri="1.2.3.4:8080")

    result = deduplicate_nodes([n1, n2])

    assert len(result) == 1


def test_dedup_keeps_node_with_longer_raw_uri():
    """同一 protocol://server:port key 下保留 raw_uri 更长（信息更完整）的节点"""
    n1 = Node(
        protocol=Protocol.HTTP,
        server="1.2.3.4",
        port=8080,
        raw_uri="1.2.3.4:8080",
    )
    n2 = Node(
        protocol=Protocol.HTTP,
        server="1.2.3.4",
        port=8080,
        raw_uri="1.2.3.4:8080 extra-info-here",
    )

    result = deduplicate_nodes([n1, n2])

    assert len(result) == 1
    assert len(result[0].raw_uri) > len(n1.raw_uri)


def test_dedup_keeps_node_with_clash_proxy():
    """同一 key 下保留有 clash_proxy 的节点"""
    n1 = Node(
        protocol=Protocol.VMESS,
        server="example.com",
        port=443,
        raw_uri="vmess://test",
    )
    n2 = Node(
        protocol=Protocol.VMESS,
        server="example.com",
        port=443,
        raw_uri="vmess://test",
        clash_proxy={"name": "test", "type": "vmess", "server": "example.com", "port": 443},
    )

    result = deduplicate_nodes([n1, n2])

    assert len(result) == 1
    assert result[0].clash_proxy is not None


def test_dedup_skips_nodes_without_server_or_port():
    """没有 server 或 port 的节点应被跳过"""
    n1 = Node(protocol=Protocol.HTTP, server="", port=8080)
    n2 = Node(protocol=Protocol.HTTP, server="1.2.3.4", port=0)

    result = deduplicate_nodes([n1, n2])

    assert len(result) == 0


def test_dedup_empty_list():
    assert deduplicate_nodes([]) == []
