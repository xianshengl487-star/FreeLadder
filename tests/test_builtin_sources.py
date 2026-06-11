# path: tests/test_builtin_sources.py
"""测试内置免费订阅源模块"""

import pytest

from freeladder.core.builtin_sources import (
    BUILTIN_SOURCES,
    detect_public_ip,
    get_builtin_sources,
    get_builtin_source_info,
)


class TestBuiltinSources:

    def test_sources_is_nonempty_list(self):
        assert isinstance(BUILTIN_SOURCES, list)
        assert len(BUILTIN_SOURCES) > 0

    def test_each_source_has_required_fields(self):
        for src in BUILTIN_SOURCES:
            assert "name" in src, f"Source missing 'name': {src}"
            assert "url" in src, f"Source missing 'url': {src}"
            assert "format" in src, f"Source missing 'format': {src}"
            assert src["url"].startswith("http"), f"URL must start with http: {src['url']}"
            assert src["format"] in ("clash", "base64"), f"Unknown format: {src['format']}"

    def test_no_duplicate_urls(self):
        urls = [s["url"] for s in BUILTIN_SOURCES]
        assert len(urls) == len(set(urls)), "Duplicate URLs found in BUILTIN_SOURCES"

    def test_no_duplicate_names(self):
        names = [s["name"] for s in BUILTIN_SOURCES]
        assert len(names) == len(set(names)), "Duplicate names found in BUILTIN_SOURCES"


class TestGetBuiltinSources:

    def test_returns_list_of_strings(self):
        urls = get_builtin_sources()
        assert isinstance(urls, list)
        assert len(urls) > 0
        assert all(isinstance(u, str) for u in urls)

    def test_matches_builtin_sources(self):
        urls = get_builtin_sources()
        assert urls == [s["url"] for s in BUILTIN_SOURCES]


class TestGetBuiltinSourceInfo:

    def test_returns_list_of_dicts(self):
        info = get_builtin_source_info()
        assert isinstance(info, list)
        assert len(info) > 0
        for item in info:
            assert "name" in item
            assert "url" in item
            assert "format" in item


class TestDetectPublicIp:

    def test_returns_string(self):
        result = detect_public_ip(timeout=5)
        assert isinstance(result, str)

    def test_returns_ip_or_failure(self):
        result = detect_public_ip(timeout=3)
        # Either a valid IP or "检测失败"
        assert result == "检测失败" or "." in result
