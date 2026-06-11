# path: tests/test_basic_tester.py
"""测试基础连通性测试模块"""

import pytest
from unittest.mock import patch, MagicMock
import httpx

from freeladder.core.models import Node, Protocol, TestResult
from freeladder.tester.basic_tester import (
    _build_proxy_url,
    _tcp_test,
    _http_proxy_test,
    _socks5_proxy_test,
    basic_test_node,
)
from tests.conftest import make_node


class TestBuildProxyUrl:

    def test_without_auth(self):
        url = _build_proxy_url("http", "1.2.3.4", 8080)
        assert url == "http://1.2.3.4:8080"

    def test_with_auth(self):
        url = _build_proxy_url("socks5", "1.2.3.4", 1080, "user", "pass")
        assert url == "socks5://user:pass@1.2.3.4:1080"

    def test_special_chars_in_auth(self):
        url = _build_proxy_url("http", "1.2.3.4", 8080, "u@ser", "p#ass")
        assert "u%40ser" in url
        assert "p%23ass" in url

    def test_only_username(self):
        url = _build_proxy_url("http", "1.2.3.4", 8080, "user", None)
        assert url == "http://1.2.3.4:8080"


class TestTcpTest:

    @patch("freeladder.tester.basic_tester.socket.socket")
    def test_success(self, mock_socket_cls):
        mock_sock = MagicMock()
        mock_socket_cls.return_value = mock_sock
        alive, latency = _tcp_test("1.2.3.4", 80, timeout=5.0)
        assert alive is True
        assert latency is not None
        assert latency >= 0
        mock_sock.connect.assert_called_once_with(("1.2.3.4", 80))

    @patch("freeladder.tester.basic_tester.socket.socket")
    def test_timeout(self, mock_socket_cls):
        mock_sock = MagicMock()
        mock_sock.connect.side_effect = __import__("socket").timeout("timed out")
        mock_socket_cls.return_value = mock_sock
        alive, latency = _tcp_test("1.2.3.4", 80, timeout=1.0)
        assert alive is False
        assert latency is None

    @patch("freeladder.tester.basic_tester.socket.socket")
    def test_connection_refused(self, mock_socket_cls):
        mock_sock = MagicMock()
        mock_sock.connect.side_effect = ConnectionRefusedError
        mock_socket_cls.return_value = mock_sock
        alive, latency = _tcp_test("1.2.3.4", 80)
        assert alive is False

    @patch("freeladder.tester.basic_tester.socket.socket")
    def test_os_error(self, mock_socket_cls):
        mock_sock = MagicMock()
        mock_sock.connect.side_effect = OSError("Network unreachable")
        mock_socket_cls.return_value = mock_sock
        alive, latency = _tcp_test("1.2.3.4", 80)
        assert alive is False


class TestHttpProxyTest:

    @patch("freeladder.tester.basic_tester.httpx.Client")
    def test_success_204(self, mock_client_cls):
        mock_resp = MagicMock()
        mock_resp.status_code = 204
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get.return_value = mock_resp
        mock_client_cls.return_value = mock_client

        alive, latency, error = _http_proxy_test("1.2.3.4", 8080)
        assert alive is True
        assert latency is not None
        assert error == ""

    @patch("freeladder.tester.basic_tester.httpx.Client")
    def test_success_200(self, mock_client_cls):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get.return_value = mock_resp
        mock_client_cls.return_value = mock_client

        alive, latency, error = _http_proxy_test("1.2.3.4", 8080)
        assert alive is True

    @patch("freeladder.tester.basic_tester.httpx.Client")
    def test_non_204_response(self, mock_client_cls):
        mock_resp = MagicMock()
        mock_resp.status_code = 403
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get.return_value = mock_resp
        mock_client_cls.return_value = mock_client

        alive, latency, error = _http_proxy_test("1.2.3.4", 8080)
        assert alive is False
        assert "403" in error

    @patch("freeladder.tester.basic_tester.httpx.Client")
    def test_timeout(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get.side_effect = httpx.TimeoutException("timeout")
        mock_client_cls.return_value = mock_client

        alive, latency, error = _http_proxy_test("1.2.3.4", 8080)
        assert alive is False
        assert "超时" in error

    @patch("freeladder.tester.basic_tester.httpx.Client")
    def test_general_exception(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get.side_effect = RuntimeError("something broke")
        mock_client_cls.return_value = mock_client

        alive, latency, error = _http_proxy_test("1.2.3.4", 8080)
        assert alive is False
        assert "失败" in error

    @patch("freeladder.tester.basic_tester.httpx.Client")
    def test_with_auth(self, mock_client_cls):
        mock_resp = MagicMock()
        mock_resp.status_code = 204
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get.return_value = mock_resp
        mock_client_cls.return_value = mock_client

        alive, latency, error = _http_proxy_test(
            "1.2.3.4", 8080, username="user", password="pass"
        )
        assert alive is True


class TestSocks5ProxyTest:

    @patch("freeladder.tester.basic_tester.httpx.Client")
    def test_success(self, mock_client_cls):
        mock_resp = MagicMock()
        mock_resp.status_code = 204
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get.return_value = mock_resp
        mock_client_cls.return_value = mock_client

        alive, latency, error = _socks5_proxy_test("1.2.3.4", 1080)
        assert alive is True

    @patch("freeladder.tester.basic_tester.httpx.Client")
    def test_timeout(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get.side_effect = httpx.TimeoutException("timeout")
        mock_client_cls.return_value = mock_client

        alive, latency, error = _socks5_proxy_test("1.2.3.4", 1080)
        assert alive is False
        assert "超时" in error


class TestBasicTestNode:

    @patch("freeladder.tester.basic_tester._http_proxy_test")
    @patch("freeladder.tester.basic_tester.get_config")
    def test_http_node_uses_http_test(self, mock_config, mock_http_test):
        mock_config.return_value = MagicMock(tester=MagicMock(test_url="http://test", timeout=8))
        mock_http_test.return_value = (True, 100, "")

        node = make_node(protocol=Protocol.HTTP, server="1.2.3.4", port=80)
        result = basic_test_node(node)

        assert result.alive is True
        assert result.latency == 100
        assert result.test_mode == "basic"
        mock_http_test.assert_called_once()

    @patch("freeladder.tester.basic_tester._socks5_proxy_test")
    @patch("freeladder.tester.basic_tester.get_config")
    def test_socks5_node_uses_socks5_test(self, mock_config, mock_socks5_test):
        mock_config.return_value = MagicMock(tester=MagicMock(test_url="http://test", timeout=8))
        mock_socks5_test.return_value = (True, 200, "")

        node = make_node(protocol=Protocol.SOCKS5, server="1.2.3.4", port=1080)
        result = basic_test_node(node)

        assert result.alive is True
        assert result.test_mode == "basic"
        mock_socks5_test.assert_called_once()

    @patch("freeladder.tester.basic_tester._tcp_test")
    @patch("freeladder.tester.basic_tester.get_config")
    def test_vmess_node_uses_tcp_fallback(self, mock_config, mock_tcp_test):
        mock_config.return_value = MagicMock(tester=MagicMock(test_url="http://test", timeout=8))
        mock_tcp_test.return_value = (True, 50)

        node = make_node(protocol=Protocol.VMESS, server="1.2.3.4", port=443)
        result = basic_test_node(node)

        assert result.alive is True
        assert result.test_mode == "tcp_fallback"
        mock_tcp_test.assert_called_once()

    @patch("freeladder.tester.basic_tester._tcp_test")
    @patch("freeladder.tester.basic_tester.get_config")
    def test_tcp_failure_sets_error(self, mock_config, mock_tcp_test):
        mock_config.return_value = MagicMock(tester=MagicMock(test_url="http://test", timeout=8))
        mock_tcp_test.return_value = (False, None)

        node = make_node(protocol=Protocol.VMESS, server="1.2.3.4", port=443)
        result = basic_test_node(node)

        assert result.alive is False
        assert "TCP" in result.error

    @patch("freeladder.tester.basic_tester._http_proxy_test")
    @patch("freeladder.tester.basic_tester.get_config")
    def test_exception_handling(self, mock_config, mock_http_test):
        # Simulate an unexpected exception during HTTP test execution
        mock_config.return_value = MagicMock(tester=MagicMock(test_url="http://test", timeout=8))
        mock_http_test.side_effect = RuntimeError("unexpected error")

        node = make_node(protocol=Protocol.HTTP, server="1.2.3.4", port=80)
        result = basic_test_node(node)

        assert result.alive is False
        assert "异常" in result.error

    @patch("freeladder.tester.basic_tester._http_proxy_test")
    @patch("freeladder.tester.basic_tester.get_config")
    def test_http_node_with_clash_proxy_auth(self, mock_config, mock_http_test):
        mock_config.return_value = MagicMock(tester=MagicMock(test_url="http://test", timeout=8))
        mock_http_test.return_value = (True, 100, "")

        node = make_node(
            protocol=Protocol.HTTP, server="1.2.3.4", port=80,
            clash_proxy={"username": "user", "password": "pass"},
        )
        basic_test_node(node)

        args = mock_http_test.call_args
        assert args[0][4] == "user"  # username
        assert args[0][5] == "pass"  # password

    @patch("freeladder.tester.basic_tester._http_proxy_test")
    @patch("freeladder.tester.basic_tester.get_config")
    def test_custom_test_url(self, mock_config, mock_http_test):
        mock_config.return_value = MagicMock(tester=MagicMock(test_url="http://default", timeout=8))
        mock_http_test.return_value = (True, 100, "")

        node = make_node(protocol=Protocol.HTTP, server="1.2.3.4", port=80)
        basic_test_node(node, test_url="http://custom")

        args = mock_http_test.call_args
        assert args[0][2] == "http://custom"
