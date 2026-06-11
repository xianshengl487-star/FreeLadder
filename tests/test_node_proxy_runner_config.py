"""tests/test_node_proxy_runner_config.py
验证 NodeProxySession 生成的 Mihomo 配置。
"""
from freeladder.core.models import Node, Protocol
from freeladder.browser.node_proxy_runner import NodeProxySession


def test_config_contains_only_one_proxy():
    """配置只包含一个节点"""
    node = Node(
        protocol=Protocol.VLESS,
        server="example.com",
        port=443,
        raw_uri="vless://uuid@example.com:443#test",
        clash_proxy={
            "name": "test-vless",
            "type": "vless",
            "server": "example.com",
            "port": 443,
            "uuid": "uuid",
        },
    )

    session = NodeProxySession(node)
    config = session._build_mihomo_config()

    assert len(config["proxies"]) == 1
    assert config["proxies"][0]["server"] == "example.com"
    assert config["proxies"][0]["port"] == 443


def test_config_binds_127_0_0_1():
    """配置绑定 127.0.0.1，不监听外部"""
    node = Node(
        protocol=Protocol.HTTP,
        server="1.2.3.4",
        port=8080,
        clash_proxy={
            "name": "test-http",
            "type": "http",
            "server": "1.2.3.4",
            "port": 8080,
        },
    )

    session = NodeProxySession(node)
    config = session._build_mihomo_config()

    assert config["bind-address"] == "127.0.0.1"
    assert config["allow-lan"] is False


def test_config_uses_global_mode():
    """global 模式，所有流量走代理"""
    node = Node(
        protocol=Protocol.SOCKS5,
        server="10.0.0.1",
        port=1080,
        clash_proxy={
            "name": "test-socks",
            "type": "socks5",
            "server": "10.0.0.1",
            "port": 1080,
        },
    )

    session = NodeProxySession(node)
    config = session._build_mihomo_config()

    assert config["mode"] == "global"
    assert "MATCH,Proxy" in config["rules"]


def test_config_external_controller_127_0_0_1():
    """external-controller 绑定 127.0.0.1"""
    node = Node(
        protocol=Protocol.HTTP,
        server="1.2.3.4",
        port=80,
        clash_proxy={"name": "h", "type": "http", "server": "12.3.4", "port": 80},
    )

    session = NodeProxySession(node)
    session.mixed_port = 12345
    session.external_controller_port = 12346
    config = session._build_mihomo_config()

    assert config["external-controller"] == "127.0.0.1:12346"


def test_config_has_secret():
    """配置包含 secret"""
    node = Node(
        protocol=Protocol.HTTP,
        server="1.2.3.4",
        port=80,
        clash_proxy={"name": "h", "type": "http", "server": "1.2.3.4", "port": 80},
    )

    session = NodeProxySession(node)
    config = session._build_mihomo_config()

    assert len(config["secret"]) == 32  # token_hex(16) = 32 chars


def test_config_log_level_warning():
    """日志级别为 warning，减少输出"""
    node = Node(
        protocol=Protocol.HTTP,
        server="1.2.3.4",
        port=80,
        clash_proxy={"name": "h", "type": "http", "server": "1.2.3.4", "port": 80},
    )

    session = NodeProxySession(node)
    config = session._build_mihomo_config()

    assert config["log-level"] == "warning"


def test_reject_node_without_clash_proxy():
    """无 clash_proxy 的节点无法启动"""
    node = Node(
        protocol=Protocol.VMESS,
        server="example.com",
        port=443,
    )

    session = NodeProxySession(node)
    result = session.start()
    assert result is False


def test_proxy_url_format():
    """proxy_url 格式正确"""
    node = Node(
        protocol=Protocol.HTTP,
        server="1.2.3.4",
        port=80,
        clash_proxy={"name": "h", "type": "http", "server": "1.2.3.4", "port": 80},
    )

    session = NodeProxySession(node)
    session.mixed_port = 34567
    assert session.proxy_url == "http://127.0.0.1:34567"
