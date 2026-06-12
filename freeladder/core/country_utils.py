# path: freeladder/core/country_utils.py
"""国家/地区识别与搜索工具"""

from __future__ import annotations

import re
from typing import Optional

# 搜索别名 -> 规范显示名
COUNTRY_ALIASES: dict[str, str] = {
    "us": "美国",
    "usa": "美国",
    "america": "美国",
    "united states": "美国",
    "美国": "美国",
    "北美": "美国",
    "jp": "日本",
    "japan": "日本",
    "日本": "日本",
    "hk": "香港",
    "hong kong": "香港",
    "香港": "香港",
    "tw": "台湾",
    "taiwan": "台湾",
    "台湾": "台湾",
    "sg": "新加坡",
    "singapore": "新加坡",
    "新加坡": "新加坡",
    "kr": "韩国",
    "korea": "韩国",
    "韩国": "韩国",
    "cn": "中国",
    "china": "中国",
    "中国": "中国",
    "uk": "英国",
    "britain": "英国",
    "united kingdom": "英国",
    "英国": "英国",
    "de": "德国",
    "germany": "德国",
    "德国": "德国",
    "fr": "法国",
    "france": "法国",
    "法国": "法国",
    "ca": "加拿大",
    "canada": "加拿大",
    "加拿大": "加拿大",
    "au": "澳大利亚",
    "australia": "澳大利亚",
    "澳大利亚": "澳大利亚",
    "nl": "荷兰",
    "netherlands": "荷兰",
    "荷兰": "荷兰",
    "ru": "俄罗斯",
    "russia": "俄罗斯",
    "俄罗斯": "俄罗斯",
    "in": "印度",
    "india": "印度",
    "印度": "印度",
    "tr": "土耳其",
    "turkey": "土耳其",
    "土耳其": "土耳其",
    "ir": "伊朗",
    "iran": "伊朗",
    "伊朗": "伊朗",
    "az": "阿塞拜疆",
    "阿塞拜疆": "阿塞拜疆",
    "br": "巴西",
    "brazil": "巴西",
    "巴西": "巴西",
    "ar": "阿根廷",
    "阿根廷": "阿根廷",
    "mx": "墨西哥",
    "墨西哥": "墨西哥",
    "se": "瑞典",
    "瑞典": "瑞典",
    "fi": "芬兰",
    "芬兰": "芬兰",
    "it": "意大利",
    "意大利": "意大利",
    "es": "西班牙",
    "西班牙": "西班牙",
    "th": "泰国",
    "泰国": "泰国",
    "vn": "越南",
    "越南": "越南",
    "my": "马来西亚",
    "马来西亚": "马来西亚",
    "ph": "菲律宾",
    "菲律宾": "菲律宾",
    "id": "印度尼西亚",
    "印度尼西亚": "印度尼西亚",
}

# 旗帜 emoji -> 规范名
FLAG_TO_COUNTRY: dict[str, str] = {
    "🇺🇸": "美国",
    "🇯🇵": "日本",
    "🇭🇰": "香港",
    "🇹🇼": "台湾",
    "🇸🇬": "新加坡",
    "🇰🇷": "韩国",
    "🇨🇳": "中国",
    "🇬🇧": "英国",
    "🇩🇪": "德国",
    "🇫🇷": "法国",
    "🇨🇦": "加拿大",
    "🇦🇺": "澳大利亚",
    "🇳🇱": "荷兰",
    "🇷🇺": "俄罗斯",
    "🇮🇳": "印度",
    "🇹🇷": "土耳其",
    "🇮🇷": "伊朗",
    "🇦🇿": "阿塞拜疆",
    "🇧🇷": "巴西",
    "🇦🇷": "阿根廷",
    "🇲🇽": "墨西哥",
    "🇸🇪": "瑞典",
    "🇫🇮": "芬兰",
    "🇮🇹": "意大利",
    "🇪🇸": "西班牙",
    "🇹🇭": "泰国",
    "🇻🇳": "越南",
    "🇲🇾": "马来西亚",
    "🇵🇭": "菲律宾",
    "🇮🇩": "印度尼西亚",
}

# 节点名中常见的中文国名（按长度降序，优先长匹配）
_COUNTRY_NAMES = sorted(
    {v for v in COUNTRY_ALIASES.values()},
    key=len,
    reverse=True,
)

_NAME_COUNTRY_RE = re.compile(
    r"(?:^|[\s\-_/|>（(])({countries})".format(
        countries="|".join(re.escape(c) for c in _COUNTRY_NAMES)
    )
)


def normalize_country_query(query: str) -> Optional[str]:
    """将用户输入规范化为国家显示名"""
    q = (query or "").strip()
    if not q:
        return None
    key = q.lower()
    if key in COUNTRY_ALIASES:
        return COUNTRY_ALIASES[key]
    if q in COUNTRY_ALIASES.values():
        return q
    return q


def build_country_search_patterns(query: str) -> list[str]:
    """生成用于 SQL LIKE 的搜索模式列表"""
    q = (query or "").strip()
    if not q:
        return []

    patterns: list[str] = []
    seen: set[str] = set()

    def _add(pattern: str):
        p = pattern.lower()
        if p and p not in seen:
            seen.add(p)
            patterns.append(f"%{p}%")

    _add(q)
    canonical = normalize_country_query(q)
    if canonical:
        _add(canonical)
    key = q.lower()
    if key in COUNTRY_ALIASES:
        _add(COUNTRY_ALIASES[key])
        _add(key)

    return patterns


def extract_country_from_name(name: str) -> str:
    """从节点名称提取国家/地区"""
    text = (name or "").strip()
    if not text:
        return ""

    for flag, country in FLAG_TO_COUNTRY.items():
        if flag in text:
            return country

    match = _NAME_COUNTRY_RE.search(text)
    if match:
        return match.group(1)

    upper = text.upper()
    for code, country in COUNTRY_ALIASES.items():
        if len(code) <= 3 and code.isalpha():
            if re.search(rf"\b{re.escape(code)}\b", upper):
                return country

    return ""


def apply_country_to_node(node) -> None:
    """为节点填充 country 字段（就地修改）"""
    if not getattr(node, "country", ""):
        country = extract_country_from_name(getattr(node, "name", ""))
        if country:
            node.country = country