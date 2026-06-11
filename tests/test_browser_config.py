"""tests/test_browser_config.py
验证 browser 配置可正确加载。
"""
from freeladder.core.config import Config, BrowserConfig


def test_browser_config_defaults():
    cfg = Config()
    assert cfg.browser.enabled is True
    assert cfg.browser.engine == "playwright"
    assert cfg.browser.headless is False
    assert cfg.browser.isolate_profile is True
    assert cfg.browser.control_api_port == 8787
    assert cfg.browser.allow_external_control is True
    assert cfg.browser.ai_control_enabled is True


def test_browser_config_from_dict():
    data = {
        "browser": {
            "enabled": False,
            "headless": True,
            "control_api_port": 9999,
            "default_url": "https://example.com",
        }
    }
    cfg = Config(**data)
    assert cfg.browser.enabled is False
    assert cfg.browser.headless is True
    assert cfg.browser.control_api_port == 9999
    assert cfg.browser.default_url == "https://example.com"


def test_browser_config_extension_dirs():
    cfg = BrowserConfig(extension_dirs=["/path/a", "/path/b"])
    assert len(cfg.extension_dirs) == 2
