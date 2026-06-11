#!/usr/bin/env python3
# path: tools/browser_smoke_test.py
"""FreeLadder Browser Sandbox smoke test

不依赖真实代理节点或 Chromium，只测试配置生成和 session 生命周期。
如果没有 Mihomo 或 Playwright，提示 SKIP 而非报错。
"""

import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))


def main():
    passed = 0
    failed = 0
    skipped = 0

    def check(name, condition, skip_reason=""):
        nonlocal passed, failed, skipped
        if condition:
            print(f"  PASS  {name}")
            passed += 1
        elif skip_reason:
            print(f"  SKIP  {name} ({skip_reason})")
            skipped += 1
        else:
            print(f"  FAIL  {name}")
            failed += 1

    print("FreeLadder Browser Sandbox smoke test")
    print("=" * 40)

    # 1. 导入
    print("\n[1] Import browser modules")
    try:
        from freeladder.browser import NodeProxySession, BrowserSession
        check("import browser module", True)
    except Exception as e:
        check(f"import browser module: {e}", False)

    try:
        from freeladder.browser.schemas import BrowserStartRequest, BrowserStartResponse
        check("import schemas", True)
    except Exception as e:
        check(f"import schemas: {e}", False)

    try:
        from freeladder.browser.profiles import BrowserProfile
        check("import profiles", True)
    except Exception as e:
        check(f"import profiles: {e}", False)

    # 2. 配置
    print("\n[2] Browser config")
    from freeladder.core.config import Config
    cfg = Config()
    check("browser.enabled default True", cfg.browser.enabled is True)
    check("browser.headless default False", cfg.browser.headless is False)
    check("browser.control_api_port default 8787", cfg.browser.control_api_port == 8787)
    check("browser.binds to 127.0.0.1", cfg.browser.control_api_host == "127.0.0.1")

    # 3. NodeProxySession 配置生成
    print("\n[3] NodeProxySession config generation")
    from freeladder.core.models import Node, Protocol

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

    check("config has exactly 1 proxy", len(config["proxies"]) == 1)
    check("bind-address is 127.0.0.1", config["bind-address"] == "127.0.0.1")
    check("allow-lan is False", config["allow-lan"] is False)
    check("mode is global", config["mode"] == "global")
    check("external-controller on 127.0.0.1",
          config["external-controller"].startswith("127.0.0.1:"))
    check("rules use BrowserProxy", "MATCH,BrowserProxy" in config["rules"])

    # 4. 无 clash_proxy 节点拒绝启动
    print("\n[4] Reject node without clash_proxy")
    bad_node = Node(protocol=Protocol.VMESS, server="x.com", port=443)
    bad_session = NodeProxySession(bad_node)
    result = bad_session.start()
    check("start() returns False for node without clash_proxy", result is False)

    # 5. Profile 管理
    print("\n[5] BrowserProfile")
    import tempfile
    with tempfile.TemporaryDirectory() as tmpdir:
        profile = BrowserProfile(tmpdir, "vless:abc123")
        profile.create()
        check("profile dir created", profile.profile_path.exists())
        profile.remove()
        check("profile dir removed", not profile.profile_path.exists())

    # 6. Schemas
    print("\n[6] API Schemas")
    from freeladder.browser.schemas import BrowserStartRequest
    req = BrowserStartRequest(node_id=42, url="https://example.com")
    check("schema validates node_id", req.node_id == 42)
    check("schema validates url", req.url == "https://example.com")

    # 7. Mihomo 可用性检查
    print("\n[7] Mihomo availability")
    from freeladder.core.utils import get_mihomo_path
    mihomo = get_mihomo_path()
    check("Mihomo path found", mihomo is not None,
          "Mihomo not installed - browse command will not work" if not mihomo else "")

    # 8. Playwright 可用性检查
    print("\n[8] Playwright availability")
    try:
        import playwright
        check("playwright installed", True)
    except ImportError:
        check("playwright installed", False, "pip install playwright && playwright install chromium")

    # Summary
    print("\n" + "=" * 40)
    print(f"Results: {passed} passed, {failed} failed, {skipped} skipped")

    if failed > 0:
        print("\nSome tests FAILED!")
        sys.exit(1)
    else:
        print("\nAll tests passed!")
        sys.exit(0)


if __name__ == "__main__":
    main()
