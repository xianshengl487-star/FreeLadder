"""FreeLadder Browser Sandbox

内置隔离浏览器模块，为单个节点启动独立 Chromium 实例，
通过临时 Mihomo 代理实现节点级隔离，不影响系统代理。
"""

from .node_proxy_runner import NodeProxySession
from .browser_manager import BrowserSession

__all__ = ["NodeProxySession", "BrowserSession"]
