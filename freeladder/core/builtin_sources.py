# path: freeladder/core/builtin_sources.py
"""内置免费订阅源管理模块

提供:
- 内置的公开免费代理订阅源 URL 列表
- 公网 IP 检测
- 一键爬取功能
"""

import httpx
from loguru import logger


# ─── 内置免费订阅源 ───────────────────────────────────
# 来源于 GitHub 上广泛分享的免费代理聚合项目
# 每个源持续维护，定期更新节点
BUILTIN_SOURCES: list[dict] = [
    # ── 聚合类（Clash YAML 格式，含完整 proxy dict）──
    {
        "name": "Peasoft-NoMoreWalls",
        "url": "https://raw.githubusercontent.com/peasoft/NoMoreWalls/master/list.yml",
        "format": "clash",
    },
    {
        "name": "mfuu-v2ray",
        "url": "https://raw.githubusercontent.com/mfuu/v2ray/master/v2ray",
        "format": "base64",
    },
    {
        "name": "mahdibland-V2RayAggregator",
        "url": "https://raw.githubusercontent.com/mahdibland/V2RayAggregator/master/Eternity.yml",
        "format": "clash",
    },
    {
        "name": "aiboboxx-v2rayfree",
        "url": "https://raw.githubusercontent.com/aiboboxx/v2rayfree/main/clash.yaml",
        "format": "clash",
    },
    {
        "name": "anaer-Sub",
        "url": "https://raw.githubusercontent.com/anaer/Sub/main/clash.yaml",
        "format": "clash",
    },
    {
        "name": "ermaozi-get_subscribe",
        "url": "https://raw.githubusercontent.com/ermaozi/get_subscribe/main/clash.yaml",
        "format": "clash",
    },
    {
        "name": "OPEN-VPN-01",
        "url": "https://raw.githubusercontent.com/OPEN-VPN/0/main/v2",
        "format": "base64",
    },
    {
        "name": "OPEN-VPN-02",
        "url": "https://raw.githubusercontent.com/OPEN-VPN/0/main/clash",
        "format": "clash",
    },
    {
        "name": "ripaojiedian-freenode",
        "url": "https://raw.githubusercontent.com/ripaojiedian/freenode/main/clash",
        "format": "clash",
    },
    {
        "name": "ts-sf-flying",
        "url": "https://raw.githubusercontent.com/ts-sf/flying/main/clash",
        "format": "clash",
    },
    {
        "name": "xrayfree-v2ray",
        "url": "https://raw.githubusercontent.com/xrayfree/v2rayfree/main/v2",
        "format": "base64",
    },
    {
        "name": "yebekhe-TelegramV2rayCollector",
        "url": "https://raw.githubusercontent.com/yebekhe/TelegramV2rayCollector/main/sub/base64/vless",
        "format": "base64",
    },
    {
        "name": "yebekhe-TelegramV2rayCollector-clash",
        "url": "https://raw.githubusercontent.com/yebekhe/TelegramV2rayCollector/main/sub/clash/vless",
        "format": "clash",
    },
    {
        "name": "soroushmirzaei-telegram-configs",
        "url": "https://raw.githubusercontent.com/soroushmirzaei/telegram-configs-collector/main/protocols/clash",
        "format": "clash",
    },
    {
        "name": "Leon406-SubCrawler",
        "url": "https://raw.githubusercontent.com/Leon406/SubCrawler/master/sub/share/vless",
        "format": "base64",
    },
    {
        "name": "Leon406-SubCrawler-clash",
        "url": "https://raw.githubusercontent.com/Leon406/SubCrawler/master/share/clash",
        "format": "clash",
    },
    {
        "name": "Pawdroid-Free-servers",
        "url": "https://raw.githubusercontent.com/Pawdroid/Free-servers/main/sub",
        "format": "base64",
    },
    {
        "name": "zhangkaiitugithub",
        "url": "https://raw.githubusercontent.com/zhangkaiitugithub/pass/main/Clash",
        "format": "clash",
    },
    {
        "name": "mfuu-v2ray-clash",
        "url": "https://raw.githubusercontent.com/mfuu/v2ray/master/clash.yaml",
        "format": "clash",
    },
    {
        "name": "ebmaozi-v2ray",
        "url": "https://raw.githubusercontent.com/ebmaozi/v2rayx/main/x",
        "format": "base64",
    },
    {
        "name": "misersun-clash",
        "url": "https://raw.githubusercontent.com/misersun/clashx-proxy-service/main/config.yaml",
        "format": "clash",
    },
    {
        "name": "tbbatbb-free-v2ray",
        "url": "https://raw.githubusercontent.com/tbbatbb/Proxy/master/dist/v2ray.config",
        "format": "base64",
    },
    {
        "name": "freefq-free",
        "url": "https://raw.githubusercontent.com/freefq/free/master/v2",
        "format": "base64",
    },
    {
        "name": "clashconfig",
        "url": "https://raw.githubusercontent.com/itsyebekhe/HiN-VPN/main/subscription/normal/vless",
        "format": "base64",
    },
    # ── 中东/土耳其/印度 ──
    {
        "name": "MrMohewa-Nodes",
        "url": "https://raw.githubusercontent.com/MrMohewa/Nodes/main/Clash",
        "format": "clash",
    },
    {
        "name": "MrMohewa-Nodes-Base64",
        "url": "https://raw.githubusercontent.com/MrMohewa/Nodes/main/All",
        "format": "base64",
    },
    {
        "name": "HosseinKarami27-Bestfree",
        "url": "https://raw.githubusercontent.com/HosseinKarami27/Bestfree/main/Clash",
        "format": "clash",
    },
    {
        "name": "HosseinKarami27-Bestfree-Base64",
        "url": "https://raw.githubusercontent.com/HosseinKarami27/Bestfree/main/Vless",
        "format": "base64",
    },
    {
        "name": "sadevans-SUB",
        "url": "https://raw.githubusercontent.com/sadevans/SUB/main/sub-clash-yaml",
        "format": "clash",
    },
    {
        "name": "AliMohaMadi-Naproxy",
        "url": "https://raw.githubusercontent.com/AliMohaMadi/Naproxy/main/All_Configs_Sub.txt",
        "format": "base64",
    },
    {
        "name": "Epodonios-v2ray-configs",
        "url": "https://raw.githubusercontent.com/Epodonios/v2ray-configs/main/All_Configs_Sub.txt",
        "format": "base64",
    },
    # ── 拉丁美洲/西班牙语 ──
    {
        "name": "AresS31-v2ray-free",
        "url": "https://raw.githubusercontent.com/AresS31/v2ray-free/main/clash.yaml",
        "format": "clash",
    },
    {
        "name": "RiriIsmail-sub",
        "url": "https://raw.githubusercontent.com/RiriIsmail/sub/main/clash",
        "format": "clash",
    },
    # ── 欧洲/多语言 ──
    {
        "name": "LalatinaHub-v2ray",
        "url": "https://raw.githubusercontent.com/LalatinaHub/Inventory/main/Merge/clash.yaml",
        "format": "clash",
    },
    {
        "name": "LalatinaHub-v2ray-base64",
        "url": "https://raw.githubusercontent.com/LalatinaHub/Inventory/main/Merge/V2RAY.txt",
        "format": "base64",
    },
    {
        "name": "barry-far-V2ray-Configs",
        "url": "https://raw.githubusercontent.com/barry-far/V2ray-Configs/main/All_Configs_Sub.txt",
        "format": "base64",
    },
    {
        "name": "MrMohebi-v2ray-rotation",
        "url": "https://raw.githubusercontent.com/MrMohebi/xray-proxy-grabber-telegram/master/best_configs/all_configs.yml",
        "format": "clash",
    },
    # ── 多协议聚合 ──
    {
        "name": "vxiaov-free_proxies",
        "url": "https://raw.githubusercontent.com/vxiaov/free_proxies/main/clash/clash.provider.yaml",
        "format": "clash",
    },
    {
        "name": "xiaoji235-airport-free",
        "url": "https://raw.githubusercontent.com/xiaoji235/airport-free/main/clash",
        "format": "clash",
    },
    {
        "name": "coldwater-10-V2RAY-CLASH",
        "url": "https://raw.githubusercontent.com/coldwater-10/V2RAY-and-CLASH-Subscription-Links/main/Clash",
        "format": "clash",
    },
    {
        "name": "mermeroo-V2RAY-CLASH-BASE64",
        "url": "https://raw.githubusercontent.com/mermeroo/V2RAY-CLASH-BASE64-Subscription.Links/main/Clash",
        "format": "clash",
    },
    # ── jsDelivr CDN 镜像 ──
    {
        "name": "jsDelivr-learnhard",
        "url": "https://cdn.jsdelivr.net/gh/vxiaov/free_proxies@main/clash/clash.provider.yaml",
        "format": "clash",
    },
    {
        "name": "jsDelivr-Pawdroid",
        "url": "https://cdn.jsdelivr.net/gh/Pawdroid/Free-servers@main/sub",
        "format": "base64",
    },
    {
        "name": "jsDelivr-mfuu",
        "url": "https://cdn.jsdelivr.net/gh/mfuu/v2ray@master/clash.yaml",
        "format": "clash",
    },
]


def detect_public_ip(timeout: int = 8) -> str:
    """检测公网 IP 地址

    依次尝试多个 IP 检测服务:
    1. ipify.org
    2. ipinfo.io
    3. httpbin.org

    Returns:
        公网 IP 字符串，失败返回 "检测失败"
    """
    services = [
        "https://api.ipify.org?format=json",
        "https://ipinfo.io/json",
        "https://httpbin.org/ip",
    ]

    for url in services:
        try:
            with httpx.Client(timeout=timeout, follow_redirects=True) as client:
                resp = client.get(url)
                resp.raise_for_status()
                data = resp.json()
                # 不同服务返回格式不同
                if "ip" in data:
                    return str(data["ip"])
        except Exception:
            continue

    logger.warning("所有公网 IP 检测服务均失败")
    return "检测失败"


def get_builtin_sources() -> list[str]:
    """获取所有内置订阅源 URL"""
    return [s["url"] for s in BUILTIN_SOURCES]


def get_builtin_source_info() -> list[dict]:
    """获取内置订阅源详细信息（名称 + URL）"""
    return [{"name": s["name"], "url": s["url"], "format": s["format"]}
            for s in BUILTIN_SOURCES]
