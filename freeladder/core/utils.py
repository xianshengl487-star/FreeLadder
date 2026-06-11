# path: freeladder/core/utils.py
"""通用工具函数"""

import re
import socket
import time
from typing import Optional


def is_valid_ip(ip: str) -> bool:
    """验证 IP 地址格式"""
    pattern = r'^(\d{1,3}\.){3}\d{1,3}$'
    if not re.match(pattern, ip):
        return False
    return all(0 <= int(octet) <= 255 for octet in ip.split('.'))


def is_valid_port(port: int) -> bool:
    """验证端口号"""
    return 1 <= port <= 65535


def get_timestamp() -> str:
    """获取当前时间戳字符串"""
    return time.strftime("%Y-%m-%d %H:%M:%S")


def parse_server_port(host_port: str) -> tuple[str, int]:
    """解析 host:port 字符串"""
    # 处理 IPv6 [host]:port 格式
    if host_port.startswith('['):
        match = re.match(r'\[(.+?)\]:(\d+)', host_port)
        if match:
            return match.group(1), int(match.group(2))
        # [host] 无端口
        match = re.match(r'\[(.+?)\]', host_port)
        if match:
            return match.group(1), 0

    # 普通 host:port
    parts = host_port.rsplit(':', 1)
    if len(parts) == 2:
        try:
            return parts[0], int(parts[1])
        except ValueError:
            pass

    return host_port, 0


def find_free_port(start: int = 0, end: int = 65535) -> int:
    """查找空闲端口"""
    import random
    if start == 0 and end == 65535:
        # 随机选择一个端口
        port = random.randint(10000, 60000)
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            sock.bind(('127.0.0.1', port))
            return port
        except OSError:
            pass
        finally:
            sock.close()

    # 从指定范围查找
    for port in range(start, end):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            sock.bind(('127.0.0.1', port))
            return port
        except OSError:
            continue
        finally:
            sock.close()

    raise RuntimeError("未找到可用端口")


def mask_secret(secret: str) -> str:
    """隐藏敏感信息"""
    if not secret or len(secret) < 8:
        return "****"
    return secret[:4] + "****" + secret[-4:]


def make_unique_proxy_names(proxies: list[dict]) -> list[dict]:
    """
    返回一个新的 proxies 列表，保证每个 proxy 的 name 唯一。
    不会原地修改外部传入的对象。
    """
    seen: dict[str, int] = {}
    result: list[dict] = []

    for i, proxy in enumerate(proxies, 1):
        p = dict(proxy)
        base = str(p.get("name") or f"Node-{i}").strip()
        if not base:
            base = f"Node-{i}"

        count = seen.get(base, 0) + 1
        seen[base] = count

        if count == 1:
            p["name"] = base
        else:
            p["name"] = f"{base}-{count}"

        result.append(p)

    return result
