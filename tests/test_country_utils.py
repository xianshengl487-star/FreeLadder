# path: tests/test_country_utils.py
"""国家识别与搜索测试"""

from freeladder.core.country_utils import (
    build_country_search_patterns,
    extract_country_from_name,
    normalize_country_query,
)


class TestCountryUtils:
    def test_extract_from_flag_and_chinese(self):
        name = "🇯🇵 VMESS-美国>日本-NF解锁日本地区-ChatGPT-t1.example.com:8443"
        assert extract_country_from_name(name) == "日本"

    def test_extract_canada(self):
        name = "🇨🇦 SS-加拿大-NF解锁加拿大地区非自制剧"
        assert extract_country_from_name(name) == "加拿大"

    def test_normalize_jp_alias(self):
        assert normalize_country_query("JP") == "日本"
        assert normalize_country_query("日本") == "日本"

    def test_build_search_patterns(self):
        patterns = build_country_search_patterns("JP")
        assert "%jp%" in patterns
        assert "%日本%" in patterns

    def test_empty_name(self):
        assert extract_country_from_name("") == ""