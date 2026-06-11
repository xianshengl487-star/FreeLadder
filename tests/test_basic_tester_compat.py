"""tests/test_basic_tester_compat.py
静态检查 basic_tester.py 不再使用已废弃的 httpx proxies= 参数。
"""
from pathlib import Path


def test_basic_tester_does_not_use_removed_httpx_proxies_argument():
    path = Path("freeladder/tester/basic_tester.py")
    content = path.read_text(encoding="utf-8")

    assert "proxies=" not in content
    assert "proxy=proxy_url" in content
