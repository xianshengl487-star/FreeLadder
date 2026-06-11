"""tests/test_browser_api_routes.py
验证 Browser Control API 路由注册。
"""
from freeladder.browser.control_api import create_browser_api


def test_browser_api_routes_have_browser_prefix():
    app = create_browser_api()
    paths = set()
    for route in app.routes:
        if hasattr(route, "path"):
            paths.add(route.path)

    assert "/browser/status" in paths
    assert "/browser/start" in paths
    assert "/browser/stop" in paths
    assert "/browser/goto" in paths
    assert "/browser/click" in paths
    assert "/browser/fill" in paths
    assert "/browser/evaluate" in paths
    assert "/browser/screenshot" in paths
    assert "/browser/dom" in paths


def test_browser_api_no_old_root_routes():
    """旧的 /start /status 等根路径不应存在"""
    app = create_browser_api()
    paths = set()
    for route in app.routes:
        if hasattr(route, "path"):
            paths.add(route.path)

    # 这些根路径不应存在
    assert "/start" not in paths
    assert "/stop" not in paths
    assert "/status" not in paths
