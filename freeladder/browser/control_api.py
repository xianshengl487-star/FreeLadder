# path: freeladder/browser/control_api.py
"""浏览器控制 API

提供本地 HTTP API 供外部工具操作浏览器。
默认只监听 127.0.0.1，支持 token 鉴权。
"""

import asyncio
import secrets
from typing import Optional

from fastapi import FastAPI, HTTPException, Depends, Header
from loguru import logger

from freeladder.core.config import get_config
from freeladder.core.database import get_db
from .browser_manager import BrowserSession
from .schemas import (
    BrowserStartRequest,
    BrowserStartResponse,
    BrowserGotoRequest,
    BrowserClickRequest,
    BrowserFillRequest,
    BrowserEvaluateRequest,
    BrowserStatusResponse,
    BrowserErrorResponse,
    BrowserMessageResponse,
)

# 全局 session registry
_sessions: dict[str, BrowserSession] = {}
_api_token: Optional[str] = None


def _get_or_create_token() -> str:
    """获取或生成 API token"""
    global _api_token
    if _api_token is None:
        _api_token = secrets.token_hex(16)
    return _api_token


def _verify_token(authorization: Optional[str] = Header(None)) -> None:
    """验证 token"""
    cfg = get_config()
    if not cfg.browser.allow_external_control:
        raise HTTPException(status_code=403, detail="External control is disabled")

    token = _get_or_create_token()
    if authorization != f"Bearer {token}":
        raise HTTPException(status_code=401, detail="Invalid token")


def create_browser_api() -> FastAPI:
    """创建浏览器控制 API 应用"""
    app = FastAPI(
        title="FreeLadder Browser Control API",
        description="本地浏览器控制接口",
        docs_url="/docs" if get_config().browser.allow_external_control else None,
    )

    @app.on_event("startup")
    async def startup():
        _get_or_create_token()
        logger.info(f"Browser Control API started. Token: {_api_token}")

    @app.get("/status")
    async def status(authorization: Optional[str] = Header(None)):
        """获取所有浏览器会话状态"""
        _verify_token(authorization)
        result = []
        for bid, session in _sessions.items():
            result.append({
                "browser_id": bid,
                "status": "running" if session.is_running else "closed",
                "proxy": session.proxy_session.proxy_url if session.proxy_session else "",
                "node_id": session.node.id,
                "url": session.current_url,
            })
        return {"sessions": result, "count": len(result)}

    @app.post("/start", response_model=BrowserStartResponse)
    async def start_browser(
        req: BrowserStartRequest,
        authorization: Optional[str] = Header(None),
    ):
        """为指定节点启动浏览器"""
        _verify_token(authorization)

        db = get_db()
        nodes = db.get_all_nodes()
        node = None
        for n in nodes:
            if n.id == req.node_id:
                node = n
                break

        if not node:
            raise HTTPException(status_code=404, detail=f"Node {req.node_id} not found")

        if not node.clash_proxy:
            raise HTTPException(status_code=400, detail="Node has no clash_proxy data")

        browser_id = f"node-{req.node_id}-{secrets.token_hex(4)}"

        session = BrowserSession(node, req.url)
        result = await session.start()

        if result["status"] == "error":
            raise HTTPException(status_code=500, detail=result.get("error", "Start failed"))

        _sessions[browser_id] = session

        return BrowserStartResponse(
            browser_id=browser_id,
            status="running",
            proxy=result["proxy"],
            node_id=req.node_id,
        )

    @app.post("/stop")
    async def stop_browser(
        browser_id: str,
        authorization: Optional[str] = Header(None),
    ):
        """停止指定浏览器会话"""
        _verify_token(authorization)

        session = _sessions.pop(browser_id, None)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")

        await session.close()
        return BrowserMessageResponse(message="Browser stopped", browser_id=browser_id)

    @app.post("/goto")
    async def goto_url(
        browser_id: str,
        req: BrowserGotoRequest,
        authorization: Optional[str] = Header(None),
    ):
        """导航到指定 URL"""
        _verify_token(authorization)

        session = _sessions.get(browser_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")

        result = await session.goto(req.url)
        return result

    @app.post("/click")
    async def click_element(
        browser_id: str,
        req: BrowserClickRequest,
        authorization: Optional[str] = Header(None),
    ):
        """点击元素"""
        _verify_token(authorization)

        session = _sessions.get(browser_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")

        result = await session.click(req.selector)
        return result

    @app.post("/fill")
    async def fill_form(
        browser_id: str,
        req: BrowserFillRequest,
        authorization: Optional[str] = Header(None),
    ):
        """填充表单"""
        _verify_token(authorization)

        session = _sessions.get(browser_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")

        result = await session.fill(req.selector, req.text)
        return result

    @app.post("/evaluate")
    async def evaluate_script(
        browser_id: str,
        req: BrowserEvaluateRequest,
        authorization: Optional[str] = Header(None),
    ):
        """执行 JavaScript"""
        _verify_token(authorization)

        session = _sessions.get(browser_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")

        result = await session.evaluate(req.script)
        return result

    @app.get("/screenshot")
    async def screenshot(
        browser_id: str,
        authorization: Optional[str] = Header(None),
    ):
        """截取当前页面截图"""
        _verify_token(authorization)

        session = _sessions.get(browser_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")

        image_bytes = await session.screenshot()
        if not image_bytes:
            raise HTTPException(status_code=500, detail="Screenshot failed")

        from fastapi.responses import Response
        return Response(content=image_bytes, media_type="image/png")

    @app.get("/dom")
    async def get_dom(
        browser_id: str,
        authorization: Optional[str] = Header(None),
    ):
        """获取页面 DOM 文本"""
        _verify_token(authorization)

        session = _sessions.get(browser_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")

        text = await session.get_dom_text()
        return {"text": text}

    return app
