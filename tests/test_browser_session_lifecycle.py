"""tests/test_browser_session_lifecycle.py
验证 BrowserSession 初始化和生命周期（不启动真实 Chromium）。
"""
from freeladder.core.models import Node, Protocol
from freeladder.core.config import Config
from freeladder.browser.browser_manager import BrowserSession


def test_browser_session_has_browser_id():
    node = Node(
        id=42,
        protocol=Protocol.VLESS,
        server="example.com",
        port=443,
        raw_uri="vless://uuid@example.com:443#test",
    )
    session = BrowserSession(node)
    assert session.browser_id.startswith("node-42-")
    assert len(session.browser_id) > 10


def test_browser_session_unknown_id():
    node = Node(
        protocol=Protocol.VLESS,
        server="example.com",
        port=443,
    )
    session = BrowserSession(node)
    assert session.browser_id.startswith("node-unknown-")


def test_browser_session_default_url():
    cfg = Config()
    node = Node(protocol=Protocol.HTTP, server="1.2.3.4", port=80)
    session = BrowserSession(node)
    assert session.start_url == cfg.browser.default_url


def test_browser_session_custom_url():
    node = Node(protocol=Protocol.HTTP, server="1.2.3.4", port=80)
    session = BrowserSession(node, start_url="https://example.com")
    assert session.start_url == "https://example.com"


def test_browser_session_not_running_initially():
    node = Node(protocol=Protocol.HTTP, server="1.2.3.4", port=80)
    session = BrowserSession(node)
    assert session.is_running is False
    assert session.current_url == ""


def test_browser_session_close_when_not_started():
    """close() 在未启动时不报错"""
    import asyncio

    node = Node(protocol=Protocol.HTTP, server="1.2.3.4", port=80)
    session = BrowserSession(node)

    async def _close():
        await session.close()

    # 不应抛出异常
    asyncio.run(_close())
    assert session.is_running is False
