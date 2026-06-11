# path: freeladder/browser/schemas.py
"""Browser Sandbox API 数据模型"""

from typing import Optional
from pydantic import BaseModel, Field


class BrowserStartRequest(BaseModel):
    """启动浏览器请求"""
    node_id: int = Field(..., description="节点 ID")
    url: Optional[str] = Field(None, description="初始打开的 URL，留空使用默认")


class BrowserStartResponse(BaseModel):
    """启动浏览器响应"""
    browser_id: str
    status: str
    proxy: str
    node_id: int
    url: str = ""
    profile: str = ""


class BrowserActionResponse(BaseModel):
    """浏览器操作响应（goto/click/fill/evaluate 等）"""
    status: str
    browser_id: str = ""
    url: str = ""
    result: Optional[str] = None
    error: str = ""


class BrowserStopRequest(BaseModel):
    """停止浏览器请求"""
    browser_id: str


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
    profile: str = ""


class BrowserScreenshotResponse(BaseModel):
    """截图响应"""
    browser_id: str
    image: str = ""  # base64 encoded


class BrowserDomResponse(BaseModel):
    """DOM 文本响应"""
    browser_id: str
    text: str


class BrowserMessageResponse(BaseModel):
    """通用消息响应"""
    message: str
    browser_id: str = ""


class BrowserErrorResponse(BaseModel):
    """错误响应"""
    error: str
