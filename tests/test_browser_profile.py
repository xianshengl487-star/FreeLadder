"""tests/test_browser_profile.py
验证浏览器 profile 管理。
"""
import tempfile
from pathlib import Path

from freeladder.browser.profiles import BrowserProfile


def test_browser_profile_create_and_remove():
    with tempfile.TemporaryDirectory() as tmpdir:
        profile = BrowserProfile(tmpdir, "vless:abc123def456")
        profile.create()
        assert profile.profile_path.exists()
        assert profile.profile_path.is_dir()

        profile.remove()
        assert not profile.profile_path.exists()


def test_browser_profile_context_manager():
    with tempfile.TemporaryDirectory() as tmpdir:
        profile = BrowserProfile(tmpdir, "vmess:xyz789")
        with profile:
            assert profile.profile_path.exists()
        assert not profile.profile_path.exists()


def test_browser_profile_safe_name():
    with tempfile.TemporaryDirectory() as tmpdir:
        profile = BrowserProfile(tmpdir, "http://1.2.3.4:8080")
        # 冒号和斜线应被替换
        assert ":" not in profile.profile_path.name
        assert "/" not in profile.profile_path.name
