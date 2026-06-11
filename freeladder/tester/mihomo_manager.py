# path: freeladder/tester/mihomo_manager.py
"""Mihomo 进程管理模块

负责:
- 查找 Mihomo 二进制文件
- 生成临时配置文件
- 启动/停止 Mihomo 进程
- 管理 External Controller API
"""

import json
import os
import signal
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Optional

import httpx
from loguru import logger

from freeladder.core.config import get_config
from freeladder.core.utils import find_free_port, mask_secret
from freeladder.core.models import Node


def _find_mihomo_binary(config_path: str = "") -> Optional[str]:
    """查找 Mihomo 可执行文件

    查找顺序:
    1. config 中指定的 binary_path
    2. 项目目录 bin/mihomo.exe (Windows) 或 bin/mihomo (Linux/Mac)
    3. 系统 PATH 中的 mihomo
    4. 系统 PATH 中的 clash-meta
    """
    import sys
    import shutil

    # 1. 检查配置
    if config_path and os.path.isfile(config_path):
        return config_path

    # 2. 检查项目 bin 目录
    from freeladder.core.paths import get_project_root
    root = get_project_root()

    if sys.platform == "win32":
        candidates = [
            root / "bin" / "mihomo.exe",
            root / "bin" / "clash-meta.exe",
        ]
    else:
        candidates = [
            root / "bin" / "mihomo",
            root / "bin" / "clash-meta",
        ]

    for path in candidates:
        if path.is_file():
            logger.info(f"找到 Mihomo: {path}")
            return str(path)

    # 3. 检查系统 PATH
    for name in ["mihomo", "clash-meta"]:
        found = shutil.which(name)
        if found:
            logger.info(f"在 PATH 中找到 {name}: {found}")
            return found

    logger.warning("未找到 Mihomo 可执行文件")
    return None


def _generate_config(
    proxies: list[dict],
    mixed_port: int,
    ec_port: int,
    secret: str,
) -> dict:
    """生成 Mihomo 临时配置"""
    proxy_names = [p.get("name", f"proxy-{i}") for i, p in enumerate(proxies)]

    config = {
        "mixed-port": mixed_port,
        "allow-lan": False,
        "mode": "rule",
        "log-level": "warning",
        "external-controller": f"127.0.0.1:{ec_port}",
        "secret": secret,
        "proxies": proxies,
        "proxy-groups": [
            {
                "name": "FreeLadder-Test",
                "type": "select",
                "proxies": ["DIRECT"] + proxy_names,
            }
        ],
        "rules": [
            "MATCH,DIRECT"
        ],
    }
    return config


class MihomoManager:
    """Mihomo 进程管理器"""

    def __init__(self):
        self._config = get_config()
        self._process: Optional[subprocess.Popen] = None
        self._config_path: Optional[str] = None
        self._mixed_port: int = 0
        self._ec_port: int = 0
        self._secret: str = ""
        self._binary_path: Optional[str] = None

    @property
    def binary_path(self) -> Optional[str]:
        if self._binary_path is None:
            self._binary_path = _find_mihomo_binary(self._config.mihomo.binary_path)
        return self._binary_path

    @property
    def is_available(self) -> bool:
        return self.binary_path is not None

    @property
    def ec_url(self) -> str:
        return f"http://127.0.0.1:{self._ec_port}"

    @property
    def mixed_port(self) -> int:
        return self._mixed_port

    @property
    def secret(self) -> str:
        return self._secret

    def start(self, proxies: list[dict]) -> bool:
        """启动 Mihomo 进程

        Args:
            proxies: 代理节点列表（dict 格式）

        Returns:
            是否成功启动
        """
        if not self.is_available:
            logger.error("Mihomo 不可用，无法启动")
            return False

        if self._process and self._process.poll() is None:
            logger.warning("Mihomo 已在运行中")
            return True

        # 分配端口
        self._mixed_port = self._config.mihomo.mixed_port
        if self._mixed_port == 0:
            self._mixed_port = find_free_port(10000, 60000)

        self._ec_port = self._config.mihomo.external_controller_port
        if self._ec_port == 0:
            self._ec_port = find_free_port(10000, 60000)

        self._secret = self._config.mihomo.secret
        if not self._secret:
            import secrets
            self._secret = secrets.token_hex(16)

        # 生成配置
        config_data = _generate_config(
            proxies, self._mixed_port, self._ec_port, self._secret
        )

        # 写入临时配置文件
        tmp_dir = tempfile.mkdtemp(prefix="freeladder_mihomo_")
        self._config_path = os.path.join(tmp_dir, "config.yaml")

        import yaml
        with open(self._config_path, "w", encoding="utf-8") as f:
            yaml.dump(config_data, f, default_flow_style=False, allow_unicode=True)

        logger.info(f"Mihomo 临时配置: {self._config_path}")
        logger.info(f"  mixed-port: {self._mixed_port}")
        logger.info(f"  external-controller: 127.0.0.1:{self._ec_port}")
        logger.info(f"  secret: {mask_secret(self._secret)}")
        logger.info(f"  proxies: {len(proxies)} 个")

        # 启动进程
        try:
            cmd = [self.binary_path, "-d", tmp_dir]
            self._process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0,
            )
            logger.info(f"Mihomo 进程已启动 (PID: {self._process.pid})")
        except Exception as e:
            logger.error(f"Mihomo 启动失败: {e}")
            self._cleanup()
            return False

        # 等待 API 就绪
        if not self._wait_api_ready():
            logger.error("Mihomo API 未就绪，进程可能已退出")
            self.stop()
            return False

        logger.info("Mihomo 已就绪")
        return True

    def _wait_api_ready(self) -> bool:
        """等待 External Controller API 就绪"""
        timeout = self._config.mihomo.startup_timeout
        start = time.time()

        while time.time() - start < timeout:
            if self._process and self._process.poll() is not None:
                stderr = ""
                try:
                    stderr = self._process.stderr.read().decode("utf-8", errors="ignore")
                except Exception:
                    pass
                logger.error(f"Mihomo 进程已退出，退出码: {self._process.returncode}")
                if stderr:
                    logger.error(f"stderr: {stderr[:500]}")
                return False

            try:
                with httpx.Client(timeout=2) as client:
                    resp = client.get(
                        f"{self.ec_url}/configs",
                        headers={"Authorization": f"Bearer {self._secret}"},
                    )
                    if resp.status_code in (200, 304):
                        return True
            except Exception:
                pass

            time.sleep(0.3)

        return False

    def test_proxy_delay(
        self,
        proxy_name: str,
        timeout: int = 8000,
        url: str = "https://www.gstatic.com/generate_204",
    ) -> tuple[bool, Optional[int], str]:
        """测试单个代理延迟

        通过 Mihomo External Controller API 测试。

        Returns:
            (alive, latency_ms, error_message)
        """
        if not self._process or self._process.poll() is not None:
            return False, None, "Mihomo 未运行"

        from urllib.parse import quote
        encoded_name = quote(proxy_name, safe="")
        api_url = (
            f"{self.ec_url}/proxies/{encoded_name}/delay"
            f"?timeout={timeout}&url={quote(url, safe='')}"
        )

        try:
            with httpx.Client(timeout=timeout / 1000 + 2) as client:
                resp = client.get(
                    api_url,
                    headers={"Authorization": f"Bearer {self._secret}"},
                )
                if resp.status_code == 200:
                    data = resp.json()
                    delay = data.get("delay", 0)
                    if delay > 0:
                        return True, delay, ""
                    return False, None, "延迟为 0"
                else:
                    error_msg = resp.text[:200]
                    return False, None, f"API 错误 {resp.status_code}: {error_msg}"
        except httpx.TimeoutException:
            return False, None, "Mihomo API 超时"
        except Exception as e:
            return False, None, f"Mihomo API 异常: {e}"

    def test_batch_delay(
        self,
        proxy_names: list[str],
        timeout: int = 8000,
        url: str = "https://www.gstatic.com/generate_204",
    ) -> dict[str, tuple[bool, Optional[int], str]]:
        """批量测试代理延迟

        Returns:
            {proxy_name: (alive, latency_ms, error)}
        """
        results = {}
        for name in proxy_names:
            alive, latency, error = self.test_proxy_delay(name, timeout, url)
            results[name] = (alive, latency, error)
        return results

    def get_configs(self) -> Optional[dict]:
        """获取 Mihomo 当前配置"""
        try:
            with httpx.Client(timeout=5) as client:
                resp = client.get(
                    f"{self.ec_url}/configs",
                    headers={"Authorization": f"Bearer {self._secret}"},
                )
                if resp.status_code == 200:
                    return resp.json()
        except Exception as e:
            logger.debug(f"获取 Mihomo 配置失败: {e}")
        return None

    def stop(self):
        """停止 Mihomo 进程"""
        if self._process:
            try:
                self._process.terminate()
                try:
                    self._process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self._process.kill()
                    self._process.wait(timeout=3)
                logger.info("Mihomo 进程已停止")
            except Exception as e:
                logger.error(f"停止 Mihomo 失败: {e}")
            finally:
                self._process = None

        self._cleanup()

    def _cleanup(self):
        """清理临时文件"""
        if self._config_path:
            try:
                config_dir = Path(self._config_path).parent
                if config_dir.exists():
                    import shutil
                    shutil.rmtree(config_dir, ignore_errors=True)
                    logger.debug(f"已清理临时目录: {config_dir}")
            except Exception as e:
                logger.debug(f"清理临时文件失败: {e}")
            self._config_path = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()
        return False

    def __del__(self):
        try:
            self.stop()
        except Exception:
            pass
