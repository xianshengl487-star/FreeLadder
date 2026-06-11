"""tests/test_mihomo_fallback.py
验证 Mihomo 不存在且允许 fallback 时，不会产生 mihomo_missing 失败结果。
"""
from freeladder.core.models import Node, Protocol, TestResult as TestResultModel
from freeladder.core.config import get_config


class FakeDB:
    def __init__(self, nodes):
        self._nodes = nodes
        self.saved = []

    def get_all_nodes(self):
        return self._nodes

    def get_testable_nodes(self):
        return self._nodes

    def get_alive_nodes(self):
        return []

    def update_test_result(self, result):
        self.saved.append(result)


def test_mihomo_missing_uses_tcp_fallback(monkeypatch):
    """Mihomo 不可用 + tcp_fallback=True → test_mode 应为 tcp_fallback，不是 mihomo_missing"""
    node = Node(
        id=1,
        protocol=Protocol.VLESS,
        server="127.0.0.1",
        port=1,
        raw_uri="vless://uuid@127.0.0.1:1#test",
    )

    db = FakeDB([node])

    # 强制配置
    config = get_config()
    monkeypatch.setattr(config.tester, "prefer_mihomo", True)
    monkeypatch.setattr(config.tester, "tcp_fallback", True)

    # Mock MihomoManager.is_available = False
    class FakeManager:
        @property
        def is_available(self):
            return False

    monkeypatch.setattr(
        "freeladder.tester.test_service.MihomoManager",
        lambda: FakeManager(),
    )

    # Mock basic_test_node 返回 TCP fallback 结果
    def fake_basic_test_node(n, test_url=None):
        return TestResultModel(
            node_id=n.id,
            node_key=n.node_key,
            alive=False,
            error="TCP 连接失败",
            test_mode="tcp_fallback",
        )

    monkeypatch.setattr(
        "freeladder.tester.test_service.basic_test_node",
        fake_basic_test_node,
    )

    from freeladder.tester.test_service import TestService
    service = TestService(db)
    results = service.test_all()

    assert len(results) == 1
    assert results[0].test_mode == "tcp_fallback"
    assert results[0].test_mode != "mihomo_missing"


def test_mihomo_missing_marks_mihomo_missing_when_no_fallback(monkeypatch):
    """Mihomo 不可用 + tcp_fallback=False → test_mode 应为 mihomo_missing"""
    node = Node(
        id=1,
        protocol=Protocol.VMESS,
        server="1.2.3.4",
        port=443,
        raw_uri="vmess://test",
    )

    db = FakeDB([node])

    config = get_config()
    monkeypatch.setattr(config.tester, "prefer_mihomo", True)
    monkeypatch.setattr(config.tester, "tcp_fallback", False)

    class FakeManager:
        @property
        def is_available(self):
            return False

    monkeypatch.setattr(
        "freeladder.tester.test_service.MihomoManager",
        lambda: FakeManager(),
    )

    from freeladder.tester.test_service import TestService
    service = TestService(db)
    results = service.test_all()

    assert len(results) == 1
    assert results[0].test_mode == "mihomo_missing"
    assert results[0].alive is False
