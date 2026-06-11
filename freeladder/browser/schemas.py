# path: freeladder/browser/schemas.py
"""Browser Control API 请求/响应 schemas"""

from typing import Optional
from pydantic import BaseModel, Field


class BrowserStartRequest(BaseModel):
    """启动浏览器请求"""
    node_id: int
    url: Optional[str] = None


class BrowserStartResponse(BaseModel):
    """启动浏览器响应"""
    browser_id: str
    status: str
    proxy: str
    node_id: int


class BrowserGotoRequest(BaseModel):
    """导航请求"""
    url: str


class BrowserClickRequest(BaseModel):
    """点击请求"""
    selector: str


class BrowserFillRequest(BaseModel):
    """填充请求"""
    selector: str
    text: str


class BrowserEvaluateRequest(BaseModel):
    """执行脚本请求"""
    script: str


class BrowserStatusResponse(BaseModel):
    """浏览器状态响应"""
    browser_id: str
    status: str
    proxy: str
    node_id: int
    url: str = ""


class BrowserErrorResponse(BaseModel):
    """错误响应"""
    error: str


class BrowserMessageResponse(BaseModel):
    """通用消息响应"""
    message: str
    browser_id: str = ""
