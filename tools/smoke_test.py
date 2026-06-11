#!/usr/bin/env python3
# path: tools/smoke_test.py
"""FreeLadder 基础 smoke test

无需真实网络或订阅源，验证核心模块可正常工作。
"""

import sys
from pathlib import Path

# 确保项目根目录在 sys.path 中
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))


def main():
    passed = 0
    failed = 0

    def check(name, condition):
        nonlocal passed, failed
        if condition:
            print(f"  PASS  {name}")
            passed += 1
        else:
            print(f"  FAIL  {name}")
            failed += 1

    print("FreeLadder smoke test")
    print("=" * 40)

    # 1. 导入核心模块
    print("\n[1] Import core modules")
    try:
        from freeladder.core.models import Node, Protocol, TestResult, ExportOptions
        check("import models", True)
    except Exception as e:
        check(f"import models: {e}", False)

    try:
        from freeladder.core.dedup import deduplicate_nodes
        check("import dedup", True)
    except Exception as e:
        check(f"import dedup: {e}", False)

    try:
        from freeladder.scraper.sources import extract_nodes_from_clash_yaml
        check("import clash yaml parser", True)
    except Exception as e:
        check(f"import clash yaml parser: {e}", False)

    try:
        from freeladder.exporter.clash_exporter import get_clash_yaml_string
        check("import clash exporter", True)
    except Exception as e:
        check(f"import clash exporter: {e}", False)

    # 2. Node 模型
    print("\n[2] Node model")
    n1 = Node(protocol=Protocol.HTTP, server="1.2.3.4", port=8080, raw_uri="1.2.3.4:8080")
    check("plain http node_key", n1.node_key == "http://1.2.3.4:8080")

    n2 = Node(
        protocol=Protocol.VLESS,
        server="example.com",
        port=443,
        raw_uri="vless://uuid-1@example.com:443?security=tls#A",
    )
    n3 = Node(
        protocol=Protocol.VLESS,
        server="example.com",
        port=443,
        raw_uri="vless://uuid-2@example.com:443?security=tls#B",
    )
    check("different vless nodes have different keys", n2.node_key != n3.node_key)

    # 3. 去重
    print("\n[3] Dedup")
    nodes = [
        Node(protocol=Protocol.HTTP, server="1.2.3.4", port=8080, raw_uri="1.2.3.4:8080"),
        Node(protocol=Protocol.HTTP, server="1.2.3.4", port=8080, raw_uri="1.2.3.4:8080"),
        n2,
        n3,
    ]
    deduped = deduplicate_nodes(nodes)
    check("dedup 4 nodes -> 3 (2 same http + 2 different vless)", len(deduped) == 3)

    # 4. Clash YAML 解析
    print("\n[4] Clash YAML parser")
    yaml_content = """
proxies:
  - name: test-vless
    type: vless
    server: example.com
    port: 443
    uuid: uuid-1
    tls: true
"""
    parsed = extract_nodes_from_clash_yaml(yaml_content)
    check("parse 1 vless node from yaml", len(parsed) == 1)
    check("uuid preserved", parsed[0].clash_proxy.get("uuid") == "uuid-1")
    check("tls preserved", parsed[0].clash_proxy.get("tls") is True)

    # 5. Clash 导出
    print("\n[5] Clash export")
    clash_yaml = get_clash_yaml_string(parsed)
    check("yaml contains proxies:", "proxies:" in clash_yaml)
    check("yaml contains node name", "test-vless" in clash_yaml)

    # 6. make_unique_proxy_names
    print("\n[6] make_unique_proxy_names")
    from freeladder.core.utils import make_unique_proxy_names

    proxies = [
        {"name": "A", "type": "http", "server": "a.com", "port": 80},
        {"name": "A", "type": "http", "server": "a.com", "port": 80},
        {"name": "B", "type": "socks5", "server": "b.com", "port": 1080},
    ]
    unique = make_unique_proxy_names(proxies)
    names = [p["name"] for p in unique]
    check("unique names: A, A-2, B", names == ["A", "A-2", "B"])

    # Summary
    print("\n" + "=" * 40)
    print(f"Results: {passed} passed, {failed} failed")

    if failed > 0:
        print("\nSome tests FAILED!")
        sys.exit(1)
    else:
        print("\nAll tests passed!")
        sys.exit(0)


if __name__ == "__main__":
    main()
