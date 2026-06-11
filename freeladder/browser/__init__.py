# path: freeladder/browser/__init__.py
"""FreeLadder Browser Sandbox

为单个节点启动独立 Chromium 浏览器，通过临时 Mihomo 代理实现节点级隔离。
"""

from .node_proxy_runner import NodeProxySession
from .browser_manager import BrowserSession
from .control_api import create_browser_api

__all__ = ["NodeProxySession", "BrowserSession", "create_browser_api"]
