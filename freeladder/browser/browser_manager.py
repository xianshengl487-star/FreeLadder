# path: freeladder/browser/browser_manager.py
"""浏览器管理器

使用 Playwright 启动独立 Chromium 浏览器实例，
通过 NodeProxySession 提供的代理访问网络。
"""

import asyncio
from typing import Optional

from loguru import logger

from freeladder.core.config import get_config
from freeladder.core.models import Node
from .node_proxy_runner import NodeProxySession


class BrowserSession:
    """管理单个浏览器会话"""

    def __init__(self, node: Node, start_url: Optional[str] = None):
        self.node = node
        self.start_url = start_url or get_config().browser.default_url
        self.proxy_session: Optional[NodeProxySession] = None
        self._playwright = None
        self._browser = None
        self._context = None
        self._page = None

    @property
    def is_running(self) -> bool:
        return self._page is not None and not self._page.is_closed()

    @property
    def current_url(self) -> str:
        if self._page:
            return self._page.url
        return ""

    async def start(self) -> dict:
        """启动浏览器

        Returns:
            包含 status, proxy, browser_id 等信息的字典
        """
        from playwright.async_api import async_playwright

        # 启动代理
        self.proxy_session = NodeProxySession(self.node)
        if not self.proxy_session.start():
            return {"status": "error", "error": "无法启动代理"}

        try:
            self._playwright = await async_playwright().start()
            self._browser = await self._playwright.chromium.launch(
                headless=get_config().browser.headless,
                proxy={"server": self.proxy_session.proxy_url},
            )
            self._context = await self._browser.new_context()
            self._page = await self._context.new_page()

            if self.start_url:
                await self._page.goto(self.start_url, wait_until="domcontentloaded")

            logger.info(f"Browser started for node {self.node.node_key}")
            return {
                "status": "running",
                "proxy": self.proxy_session.proxy_url,
            }

        except Exception as e:
            logger.error(f"Browser start failed: {e}")
            await self.close()
            return {"status": "error", "error": str(e)}

    async def goto(self, url: str) -> dict:
        """导航到指定 URL"""
        if not self._page:
            return {"status": "error", "error": "Browser not started"}
        try:
            await self._page.goto(url, wait_until="domcontentloaded")
            return {"status": "ok", "url": self._page.url}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    async def screenshot(self) -> Optional[bytes]:
        """截取当前页面截图"""
        if not self._page:
            return None
        try:
            return await self._page.screenshot()
        except Exception as e:
            logger.error(f"Screenshot failed: {e}")
            return None

    async def click(self, selector: str) -> dict:
        """点击元素"""
        if not self._page:
            return {"status": "error", "error": "Browser not started"}
        try:
            await self._page.click(selector)
            return {"status": "ok"}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    async def fill(self, selector: str, text: str) -> dict:
        """填充表单"""
        if not self._page:
            return {"status": "error", "error": "Browser not started"}
        try:
            await self._page.fill(selector, text)
            return {"status": "ok"}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    async def evaluate(self, script: str) -> dict:
        """执行 JavaScript"""
        if not self._page:
            return {"status": "error", "error": "Browser not started"}
        try:
            result = await self._page.evaluate(script)
            return {"status": "ok", "result": result}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    async def get_dom_text(self) -> str:
        """获取页面 DOM 文本"""
        if not self._page:
            return ""
        try:
            return await self._page.inner_text("body")
        except Exception as e:
            logger.error(f"Get DOM text failed: {e}")
            return ""

    async def close(self) -> None:
        """关闭浏览器和代理"""
        try:
            if self._page:
                await self._page.close()
        except Exception:
            pass

        try:
            if self._context:
                await self._context.close()
        except Exception:
            pass

        try:
            if self._browser:
                await self._browser.close()
        except Exception:
            pass

        try:
            if self._playwright:
                await self._playwright.stop()
        except Exception:
            pass

        self._page = None
        self._context = None
        self._browser = None
        self._playwright = None

        if self.proxy_session:
            self.proxy_session.stop()
            self.proxy_session = None

        logger.info("Browser session closed")

    async def __aenter__(self):
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
        return False
