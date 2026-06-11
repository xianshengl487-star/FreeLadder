# path: freeladder/tester/basic_tester.py
"""基础连通性测试模块

支持 TCP 连通性测试、HTTP 代理测试、SOCKS5 代理测试。
用于 HTTP/SOCKS5 协议节点的基础检测。
"""

import socket
import time
from typing import Optional

import httpx
from loguru import logger

from freeladder.core.config import get_config
from freeladder.core.models import Node, TestResult, Protocol


def _tcp_test(server: str, port: int, timeout: float = 5.0) -> tuple[bool, Optional[int]]:
    """TCP 连通性测试

    Returns:
        (alive, latency_ms)
    """
    start = time.time()
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        sock.connect((server, port))
        latency = int((time.time() - start) * 1000)
        sock.close()
        return True, latency
    except (socket.timeout, ConnectionRefusedError, OSError) as e:
        logger.debug(f"TCP 测试失败 {server}:{port}: {e}")
        return False, None


def _http_proxy_test(
    proxy_host: str,
    proxy_port: int,
    test_url: str = "https://www.gstatic.com/generate_204",
    timeout: float = 8.0,
    username: Optional[str] = None,
    password: Optional[str] = None,
) -> tuple[bool, Optional[int], str]:
    """HTTP 代理测试

    通过 HTTP 代理访问测试 URL，检测 204 响应。

    Returns:
        (alive, latency_ms, error_message)
    """
    proxy_url = f"http://{proxy_host}:{proxy_port}"
    auth = None
    if username and password:
        auth = httpx.BasicAuth(username, password)

    start = time.time()
    try:
        with httpx.Client(
            proxies={"http://": proxy_url, "https://": proxy_url},
            timeout=timeout,
        ) as client:
            resp = client.get(test_url, auth=auth, follow_redirects=False)
            latency = int((time.time() - start) * 1000)
            # 204 或 200 都算成功
            if resp.status_code in (200, 204):
                return True, latency, ""
            return False, None, f"HTTP 状态码: {resp.status_code}"
    except httpx.TimeoutException:
        return False, None, "HTTP 代理超时"
    except Exception as e:
        return False, None, f"HTTP 代理测试失败: {e}"


def _socks5_proxy_test(
    proxy_host: str,
    proxy_port: int,
    test_url: str = "https://www.gstatic.com/generate_204",
    timeout: float = 8.0,
    username: Optional[str] = None,
    password: Optional[str] = None,
) -> tuple[bool, Optional[int], str]:
    """SOCKS5 代理测试

    通过 SOCKS5 代理访问测试 URL。

    Returns:
        (alive, latency_ms, error_message)
    """
    proxy_url = f"socks5://{proxy_host}:{proxy_port}"
    if username and password:
        proxy_url = f"socks5://{username}:{password}@{proxy_host}:{proxy_port}"

    start = time.time()
    try:
        with httpx.Client(
            proxies={"http://": proxy_url, "https://": proxy_url},
            timeout=timeout,
        ) as client:
            resp = client.get(test_url, follow_redirects=False)
            latency = int((time.time() - start) * 1000)
            if resp.status_code in (200, 204):
                return True, latency, ""
            return False, None, f"SOCKS5 状态码: {resp.status_code}"
    except httpx.TimeoutException:
        return False, None, "SOCKS5 代理超时"
    except Exception as e:
        return False, None, f"SOCKS5 代理测试失败: {e}"


def basic_test_node(node: Node, test_url: Optional[str] = None) -> TestResult:
    """对单个节点执行基础测试

    根据协议选择测试方式:
    - HTTP/HTTPS: HTTP 代理测试
    - SOCKS5: SOCKS5 代理测试
    - 其他协议: TCP 连通性测试 (fallback)
    """
    config = get_config()
    url = test_url or config.tester.test_url
    timeout = config.tester.timeout

    result = TestResult(
        node_id=node.id,
        node_key=node.node_key,
        test_mode="basic",
    )

    try:
        if node.protocol in (Protocol.HTTP, Protocol.HTTPS):
            username = None
            password = None
            if node.clash_proxy:
                username = node.clash_proxy.get("username")
                password = node.clash_proxy.get("password")
            alive, latency, error = _http_proxy_test(
                node.server, node.port, url, timeout, username, password
            )
            result.alive = alive
            result.latency = latency
            result.error = error

        elif node.protocol == Protocol.SOCKS5:
            username = None
            password = None
            if node.clash_proxy:
                username = node.clash_proxy.get("username")
                password = node.clash_proxy.get("password")
            alive, latency, error = _socks5_proxy_test(
                node.server, node.port, url, timeout, username, password
            )
            result.alive = alive
            result.latency = latency
            result.error = error

        else:
            # 其他协议: TCP fallback
            alive, latency = _tcp_test(node.server, node.port, timeout)
            result.alive = alive
            result.latency = latency
            result.test_mode = "tcp_fallback"
            if not alive:
                result.error = "TCP 连接失败"

    except Exception as e:
        result.alive = False
        result.error = f"测试异常: {e}"
        logger.error(f"节点测试异常 {node.node_key}: {e}")

    if result.alive:
        logger.debug(f"✓ {node.node_key} - {result.latency}ms")
    else:
        logger.debug(f"✗ {node.node_key} - {result.error}")

    return result
