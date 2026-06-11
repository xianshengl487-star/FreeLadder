# path: freeladder/browser/control_api.py
"""浏览器控制 API

提供本地 HTTP API 供外部工具操作浏览器。
默认只监听 127.0.0.1，支持 token 鉴权。
所有路由统一使用 /browser 前缀。
"""

import secrets
from typing import Optional

from fastapi import FastAPI, APIRouter, HTTPException, Header
from fastapi.responses import Response
from loguru import logger

from freeladder.core.config import get_config
from freeladder.core.database import get_db
from .browser_manager import BrowserSession
from .schemas import (
    BrowserStartRequest,
    BrowserStartResponse,
    BrowserStopRequest,
    BrowserGotoRequest,
    BrowserClickRequest,
    BrowserFillRequest,
    BrowserEvaluateRequest,
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
    cfg = get_config()
    app = FastAPI(
        title="FreeLadder Browser Control API",
        description="本地浏览器控制接口",
        docs_url="/docs" if cfg.browser.allow_external_control else None,
    )

    router = APIRouter(prefix="/browser")

    @app.on_event("startup")
    async def startup():
        _get_or_create_token()
        logger.info(f"Browser Control API started. Token: {_api_token}")

    @app.on_event("shutdown")
    async def shutdown():
        for session in list(_sessions.values()):
            await session.close()
        _sessions.clear()
        logger.info("Browser Control API shutdown, all sessions closed")

    @router.get("/status")
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
                "profile": str(session.profile.profile_path) if session.profile else "",
            })
        return {"sessions": result, "count": len(result)}

    @router.post("/start")
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

        session = BrowserSession(node, req.url)
        result = await session.start()

        if result["status"] == "error":
            raise HTTPException(status_code=500, detail=result.get("error", "Start failed"))

        _sessions[session.browser_id] = session

        return BrowserStartResponse(
            browser_id=session.browser_id,
            status="running",
            proxy=result["proxy"],
            node_id=req.node_id,
            url=result.get("url", ""),
            profile=result.get("profile", ""),
        )

    @router.post("/stop")
    async def stop_browser(
        req: BrowserStopRequest,
        authorization: Optional[str] = Header(None),
    ):
        """停止指定浏览器会话"""
        _verify_token(authorization)

        session = _sessions.pop(req.browser_id, None)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")

        await session.close()
        return BrowserMessageResponse(message="Browser stopped", browser_id=req.browser_id)

    @router.post("/goto")
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

    @router.post("/click")
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

    @router.post("/fill")
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

    @router.post("/evaluate")
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

    @router.get("/screenshot")
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

        return Response(content=image_bytes, media_type="image/png")

    @router.get("/dom")
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

    app.include_router(router)
    return app
