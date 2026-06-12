# path: tests/conftest.py
"""共享 pytest fixtures"""

import tempfile
from pathlib import Path

import pytest

from freeladder.core.models import Node, Protocol, TestResult, ExportOptions
from freeladder.core.config import Config, TesterConfig, ScraperConfig, MihomoConfig


@pytest.fixture
def source_store(tmp_path):
    """创建临时 SourceStore（根 conftest，供 tests/ 顶层测试使用）"""
    from freeladder.source_intel.source_store import SourceStore
    return SourceStore(data_dir=tmp_path)


def make_node(
    protocol: Protocol = Protocol.HTTP,
    server: str = "1.2.3.4",
    port: int = 8080,
    name: str = "",
    raw_uri: str = "",
    clash_proxy: dict | None = None,
    alive: bool = False,
    latency: int | None = None,
    score: float = 0.0,
    fail_count: int = 0,
    success_count: int = 0,
    last_checked: str = "",
    country: str = "",
    **kwargs,
) -> Node:
    """构建 Node 对象的工厂函数"""
    if not name:
        name = f"{protocol.value}-{server}:{port}"
    return Node(
        protocol=protocol,
        server=server,
        port=port,
        name=name,
        raw_uri=raw_uri,
        clash_proxy=clash_proxy,
        alive=alive,
        latency=latency,
        score=score,
        fail_count=fail_count,
        success_count=success_count,
        last_checked=last_checked,
        country=country,
        **kwargs,
    )


@pytest.fixture
def http_node():
    return make_node(protocol=Protocol.HTTP, server="10.0.0.1", port=80)


@pytest.fixture
def socks5_node():
    return make_node(protocol=Protocol.SOCKS5, server="10.0.0.2", port=1080)


@pytest.fixture
def vmess_node():
    return make_node(
        protocol=Protocol.VMESS,
        server="10.0.0.3",
        port=443,
        raw_uri="vmess://eyJhZGQiOiIxMC4wLjAuMyIsImFpZCI6IjAiLCJpZCI6IjEyMzQifQ==",
        clash_proxy={
            "name": "VMess-10.0.0.3:443",
            "type": "vmess",
            "server": "10.0.0.3",
            "port": 443,
            "uuid": "1234",
        },
    )


@pytest.fixture
def vless_node():
    return make_node(
        protocol=Protocol.VLESS,
        server="10.0.0.4",
        port=443,
        raw_uri="vless://uuid@10.0.0.4:443?security=tls#Test",
    )


@pytest.fixture
def trojan_node():
    return make_node(
        protocol=Protocol.TROJAN,
        server="10.0.0.5",
        port=443,
        raw_uri="trojan://password@10.0.0.5:443?sni=sni.example.com#Trojan",
    )


@pytest.fixture
def ss_node():
    return make_node(
        protocol=Protocol.SS,
        server="10.0.0.6",
        port=8388,
        raw_uri="ss://YWVzLTI1Ni1nY206cGFzc3dvcmQ=@10.0.0.6:8388#SS",
    )


@pytest.fixture
def alive_node():
    return make_node(
        alive=True,
        latency=150,
        score=85.0,
        success_count=10,
        fail_count=1,
        last_checked="2026-06-12 10:00:00",
    )


@pytest.fixture
def dead_node():
    return make_node(
        alive=False,
        latency=None,
        score=15.0,
        fail_count=8,
        success_count=2,
        last_checked="2026-06-10 10:00:00",
    )


@pytest.fixture
def test_config():
    """返回测试用 Config 实例"""
    return Config(
        scraper=ScraperConfig(sources=[], request_timeout=5, max_workers=2),
        tester=TesterConfig(
            test_url="https://httpbin.org/status/204",
            timeout=3,
            max_workers=2,
            prefer_mihomo=False,
            tcp_fallback=True,
        ),
        mihomo=MihomoConfig(binary_path=""),
    )
