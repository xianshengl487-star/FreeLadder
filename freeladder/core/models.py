# path: freeladder/core/models.py
"""数据模型定义"""

import hashlib
import time
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class Protocol(str, Enum):
    """支持的代理协议"""
    HTTP = "http"
    HTTPS = "https"
    SOCKS5 = "socks5"
    VMESS = "vmess"
    VLESS = "vless"
    TROJAN = "trojan"
    SS = "ss"
    SSR = "ssr"
    HYSTERIA = "hysteria"
    HYSTERIA2 = "hysteria2"
    TUIC = "tuic"
    UNKNOWN = "unknown"


# 高级协议列表，需要 Mihomo 才能进行真实测试
ADVANCED_PROTOCOLS = {
    Protocol.VMESS, Protocol.VLESS, Protocol.TROJAN,
    Protocol.SS, Protocol.SSR, Protocol.HYSTERIA,
    Protocol.HYSTERIA2, Protocol.TUIC,
}


class Node(BaseModel):
    """代理节点"""
    id: Optional[int] = None
    protocol: Protocol = Protocol.UNKNOWN
    server: str = ""
    port: int = 0
    name: str = ""
    raw_uri: str = ""
    clash_proxy: Optional[dict] = None
    country: str = ""
    alive: bool = False
    latency: Optional[int] = None       # 毫秒
    avg_latency: Optional[float] = None
    score: float = 0.0
    signal: str = ""
    test_mode: str = ""
    fail_count: int = 0
    success_count: int = 0
    last_error: str = ""
    source: str = ""
    created_at: str = ""
    updated_at: str = ""
    last_checked: str = ""

    @property
    def node_key(self) -> str:
        """
        生成节点唯一标识。

        规则：
        1. raw_uri 存在且包含 :// 时，优先按 raw_uri 去掉 fragment 后 hash。
        2. Clash YAML 节点 raw_uri 可能为空，但 clash_proxy 保留了完整参数。
           对高级协议，按 clash_proxy 的稳定 JSON 内容 hash（去掉 name 字段）。
        3. 普通 HTTP/SOCKS5/IP:port 节点继续使用 protocol://server:port。
        """
        if self.raw_uri and "://" in self.raw_uri:
            normalized = self.raw_uri.split("#", 1)[0].strip()
            h = hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:24]
            return f"{self.protocol.value}:{h}"

        if self.clash_proxy and self.protocol in ADVANCED_PROTOCOLS:
            import json
            proxy_data = dict(self.clash_proxy)
            # name 只是显示名，不应影响节点唯一性
            proxy_data.pop("name", None)
            normalized = json.dumps(
                proxy_data,
                sort_keys=True,
                ensure_ascii=False,
                separators=(",", ":"),
            )
            h = hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:24]
            return f"{self.protocol.value}:{h}"

        return f"{self.protocol.value}://{self.server}:{self.port}"

    @property
    def raw_hash(self) -> str:
        """生成 raw_uri 的哈希 (SHA256)"""
        if self.raw_uri:
            return hashlib.sha256(self.raw_uri.strip().encode("utf-8")).hexdigest()
        return hashlib.sha256(self.node_key.encode("utf-8")).hexdigest()

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "id": self.id,
            "protocol": self.protocol.value,
            "server": self.server,
            "port": self.port,
            "name": self.name,
            "raw_uri": self.raw_uri[:100] + "..." if len(self.raw_uri) > 100 else self.raw_uri,
            "country": self.country,
            "alive": self.alive,
            "latency": self.latency,
            "avg_latency": self.avg_latency,
            "score": round(self.score, 1),
            "signal": self.signal,
            "test_mode": self.test_mode,
            "fail_count": self.fail_count,
            "success_count": self.success_count,
            "last_error": self.last_error,
            "source": self.source,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "last_checked": self.last_checked,
        }


class TestResult(BaseModel):
    """测试结果"""
    node_id: Optional[int] = None
    node_key: str = ""
    alive: bool = False
    latency: Optional[int] = None
    error: str = ""
    test_mode: str = ""    # basic / mihomo / tcp_fallback
    tested_at: str = Field(default_factory=lambda: time.strftime("%Y-%m-%d %H:%M:%S"))


class ExportOptions(BaseModel):
    """导出选项"""
    alive_only: bool = True       # 只导出可用节点
    min_score: float = 0.0        # 最低分数
    protocols: list[str] = Field(default_factory=list)  # 协议筛选，空表示全部
    max_nodes: int = 500          # 最大节点数
    filename: str = ""            # 导出文件名
