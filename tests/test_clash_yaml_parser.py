"""tests/test_clash_yaml_parser.py
验证 Clash YAML 中的完整参数不会丢失。
"""
from freeladder.scraper.sources import extract_nodes_from_clash_yaml
from freeladder.core.dedup import deduplicate_nodes
from freeladder.core.models import Protocol


def test_extract_nodes_from_clash_yaml_keeps_full_proxy_dict():
    content = """
proxies:
  - name: test-vless
    type: vless
    server: example.com
    port: 443
    uuid: 00000000-0000-0000-0000-000000000000
    tls: true
    servername: example.com
    network: ws
    ws-opts:
      path: /path
      headers:
        Host: example.com
"""

    nodes = extract_nodes_from_clash_yaml(content)

    assert len(nodes) == 1
    node = nodes[0]
    assert node.protocol == Protocol.VLESS
    assert node.server == "example.com"
    assert node.port == 443
    assert node.clash_proxy["uuid"] == "00000000-0000-0000-0000-000000000000"
    assert node.clash_proxy["tls"] is True
    assert node.clash_proxy["ws-opts"]["path"] == "/path"


def test_extract_nodes_from_clash_yaml_skips_invalid():
    content = """
proxies:
  - name: no-server
    type: vless
    server: ""
    port: 443
  - name: no-port
    type: vless
    server: example.com
    port: 0
  - name: valid
    type: vmess
    server: good.com
    port: 443
"""

    nodes = extract_nodes_from_clash_yaml(content)

    assert len(nodes) == 1
    assert nodes[0].name == "valid"


def test_extract_nodes_from_clash_yaml_empty_or_invalid():
    assert extract_nodes_from_clash_yaml("") == []
    assert extract_nodes_from_clash_yaml("not yaml: [") == []
    assert extract_nodes_from_clash_yaml("proxies: null") == []


def test_extract_nodes_from_clash_yaml_multiple_proxies():
    content = """
proxies:
  - name: proxy-a
    type: trojan
    server: a.com
    port: 443
    password: pass1
  - name: proxy-b
    type: ss
    server: b.com
    port: 8388
    cipher: aes-256-gcm
    password: pass2
"""

    nodes = extract_nodes_from_clash_yaml(content)

    assert len(nodes) == 2
    names = {n.name for n in nodes}
    assert "proxy-a" in names
    assert "proxy-b" in names

    for node in nodes:
        assert node.clash_proxy is not None
        assert "server" in node.clash_proxy


def test_clash_yaml_same_server_port_different_uuid_not_deduped():
    """Clash YAML 同 server:port 但 uuid 不同 → 不应被去重"""
    content = """
proxies:
  - name: vless-a
    type: vless
    server: example.com
    port: 443
    uuid: uuid-a
    tls: true
  - name: vless-b
    type: vless
    server: example.com
    port: 443
    uuid: uuid-b
    tls: true
"""

    nodes = extract_nodes_from_clash_yaml(content)
    result = deduplicate_nodes(nodes)

    assert len(nodes) == 2
    assert len(result) == 2
    assert nodes[0].node_key != nodes[1].node_key


def test_clash_yaml_same_proxy_different_name_should_dedup():
    """Clash YAML 同一节点只是 name 不同 → 应去重为 1 个"""
    content = """
proxies:
  - name: name-a
    type: vless
    server: example.com
    port: 443
    uuid: same-uuid
    tls: true
  - name: name-b
    type: vless
    server: example.com
    port: 443
    uuid: same-uuid
    tls: true
"""

    nodes = extract_nodes_from_clash_yaml(content)
    result = deduplicate_nodes(nodes)

    assert len(nodes) == 2
    assert len(result) == 1
    assert nodes[0].node_key == nodes[1].node_key
