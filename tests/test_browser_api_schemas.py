"""tests/test_browser_api_schemas.py
验证 Browser Control API schema 校验。
"""
from freeladder.browser.schemas import (
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


def test_start_request_validation():
    req = BrowserStartRequest(node_id=12)
    assert req.node_id == 12
    assert req.url is None

    req2 = BrowserStartRequest(node_id=5, url="https://example.com")
    assert req2.url == "https://example.com"


def test_start_response():
    resp = BrowserStartResponse(
        browser_id="node-12-abcd",
        status="running",
        proxy="http://127.0.0.1:12345",
        node_id=12,
    )
    assert resp.browser_id == "node-12-abcd"
    assert resp.status == "running"


def test_goto_request():
    req = BrowserGotoRequest(url="https://google.com")
    assert req.url == "https://google.com"


def test_click_request():
    req = BrowserClickRequest(selector="#btn-submit")
    assert req.selector == "#btn-submit"


def test_fill_request():
    req = BrowserFillRequest(selector="input[name=q]", text="hello")
    assert req.text == "hello"


def test_evaluate_request():
    req = BrowserEvaluateRequest(script="return document.title")
    assert "document.title" in req.script


def test_status_response():
    resp = BrowserStatusResponse(
        browser_id="node-1-x",
        status="running",
        proxy="http://127.0.0.1:23456",
        node_id=1,
        url="https://example.com",
    )
    assert resp.url == "https://example.com"


def test_error_response():
    resp = BrowserErrorResponse(error="not found")
    assert resp.error == "not found"


def test_message_response():
    resp = BrowserMessageResponse(message="ok", browser_id="node-1-x")
    assert resp.message == "ok"
