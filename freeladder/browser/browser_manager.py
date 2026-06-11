# path: freeladder/browser/browser_manager.py
"""浏览器管理器

使用 Playwright 启动独立 Chromium 浏览器实例，
通过 NodeProxySession 提供的代理访问网络。
支持持久 profile 隔离和可选扩展加载。
"""

import asyncio
import secrets
from typing import Optional

from loguru import logger

from freeladder.core.config import get_config
from freeladder.core.models import Node
from .node_proxy_runner import NodeProxySession
from .profiles import BrowserProfile


class BrowserSession:
    """管理单个浏览器会话"""

    def __init__(self, node: Node, start_url: Optional[str] = None):
        self.node = node
        self.start_url = start_url or get_config().browser.default_url
        self.browser_id = self._make_browser_id(node)
        self.profile: Optional[BrowserProfile] = None
        self.proxy_session: Optional[NodeProxySession] = None
        self._playwright = None
        self._browser = None
        self._context = None
        self._page = None

    @staticmethod
    def _make_browser_id(node: Node) -> str:
        if node.id:
            return f"node-{node.id}-{secrets.token_hex(4)}"
        return f"node-unknown-{secrets.token_hex(4)}"

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
            包含 status, browser_id, proxy, node_id, url, profile 等信息
        """
        from playwright.async_api import async_playwright

        # 启动代理
        self.proxy_session = NodeProxySession(self.node)
        if not self.proxy_session.start():
            return {"status": "error", "error": "无法启动代理"}

        cfg = get_config()

        # 创建 profile（如果启用）
        if cfg.browser.isolate_profile:
            self.profile = BrowserProfile(cfg.browser.profile_dir, self.node.node_key)
            profile_path = self.profile.create()
        else:
            profile_path = None

        try:
            self._playwright = await async_playwright().start()

            # 构建启动参数
            launch_args = []
            if cfg.browser.extension_dirs:
                ext_dirs = cfg.browser.extension_dirs
                launch_args.append(f"--disable-extensions-except={','.join(ext_dirs)}")
                launch_args.append(f"--load-extension={','.join(ext_dirs)}")

            if profile_path:
                # 模式 B：持久 profile
                self._context = await self._playwright.chromium.launch_persistent_context(
                    user_data_dir=str(profile_path),
                    headless=cfg.browser.headless,
                    proxy={"server": self.proxy_session.proxy_url},
                    args=launch_args if launch_args else None,
                )
                self._page = await self._context.new_page()
            else:
                # 模式 A：普通启动
                self._browser = await self._playwright.chromium.launch(
                    headless=cfg.browser.headless,
                    proxy={"server": self.proxy_session.proxy_url},
                    args=launch_args if launch_args else None,
                )
                self._context = await self._browser.new_context()
                self._page = await self._context.new_page()

            if self.start_url:
                await self._page.goto(self.start_url, wait_until="domcontentloaded")

            logger.info(f"Browser started: {self.browser_id} via {self.proxy_session.proxy_url}")
            return {
                "status": "running",
                "browser_id": self.browser_id,
                "proxy": self.proxy_session.proxy_url,
                "node_id": self.node.id,
                "url": self.current_url,
                "profile": str(self.profile.profile_path) if self.profile else "",
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
            return {"status": "ok", "browser_id": self.browser_id, "url": self._page.url}
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
            return {"status": "ok", "browser_id": self.browser_id}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    async def fill(self, selector: str, text: str) -> dict:
        """填充表单"""
        if not self._page:
            return {"status": "error", "error": "Browser not started"}
        try:
            await self._page.fill(selector, text)
            return {"status": "ok", "browser_id": self.browser_id}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    async def evaluate(self, script: str) -> dict:
        """执行 JavaScript"""
        if not self._page:
            return {"status": "error", "error": "Browser not started"}
        try:
            result = await self._page.evaluate(script)
            return {"status": "ok", "browser_id": self.browser_id, "result": result}
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

    async def wait_closed(self):
        """阻塞等待浏览器关闭"""
        while self.is_running:
            await asyncio.sleep(1)

    async def close(self) -> None:
        """关闭浏览器、代理，清理资源"""
        cfg = get_config()

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

        # 停止代理
        if self.proxy_session:
            self.proxy_session.stop()
            self.proxy_session = None

        # 清理 profile（如果配置了关闭时删除）
        if self.profile and cfg.browser.cleanup_profile_on_close:
            self.profile.remove()
            self.profile = None

        logger.info(f"Browser session closed: {self.browser_id}")

    async def __aenter__(self):
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
        return False
