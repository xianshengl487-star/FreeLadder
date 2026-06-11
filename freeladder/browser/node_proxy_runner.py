# path: freeladder/browser/node_proxy_runner.py
"""节点代理运行器

为单个 Node 启动临时 Mihomo 实例，提供隔离代理。
每个 NodeProxySession 绑定一个随机 mixed-port，
仅监听 127.0.0.1，不影响系统其他软件。
"""

import secrets
import shutil
import subprocess
import time
from pathlib import Path
from typing import Optional

import httpx
import yaml
from loguru import logger

from freeladder.core.config import get_config
from freeladder.core.models import Node
from freeladder.core.utils import find_free_port, get_mihomo_path


class NodeProxySession:
    """为单个节点启动临时 Mihomo 代理实例"""

    def __init__(self, node: Node):
        self.node = node
        self.mixed_port: int = 0
        self.external_controller_port: int = 0
        self.secret: str = secrets.token_hex(16)
        self._process: Optional[subprocess.Popen] = None
        self._temp_dir: Optional[Path] = None

    @property
    def proxy_url(self) -> str:
        """代理 URL"""
        return f"http://127.0.0.1:{self.mixed_port}"

    @property
    def is_running(self) -> bool:
        """检查进程是否在运行"""
        if self._process is None:
            return False
        return self._process.poll() is None

    def start(self) -> bool:
        """启动临时 Mihomo 实例

        Returns:
            是否启动成功
        """
        # 校验 clash_proxy
        if not self.node.clash_proxy:
            logger.error(f"节点 {self.node.node_key} 没有 clash_proxy 数据，无法启动代理")
            return False

        # 校验 Mihomo 可用性
        mihomo_path = get_mihomo_path()
        if not mihomo_path:
            logger.error("未找到 Mihomo 二进制文件")
            return False

        # 分配端口
        self.mixed_port = find_free_port(20000, 60000)
        self.external_controller_port = find_free_port(20000, 60000)

        # 创建临时目录（在 config.data_path 下）
        cfg = get_config()
        self._temp_dir = cfg.data_path / f"tmp_browser_{self.mixed_port}"
        self._temp_dir.mkdir(parents=True, exist_ok=True)

        # 生成配置
        config = self._build_mihomo_config()
        config_path = self._temp_dir / "config.yaml"
        with open(config_path, "w", encoding="utf-8") as f:
            yaml.dump(config, f, default_flow_style=False, allow_unicode=True)

        # 启动进程
        try:
            cmd = [mihomo_path, "-d", str(self._temp_dir), "-f", str(config_path)]
            self._process = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )

            # 等待 API 就绪
            if not self._wait_ready():
                logger.error("Mihomo 代理 API 未就绪")
                self.stop()
                return False

            logger.info(f"Mihomo 代理已启动: {self.proxy_url} (PID={self._process.pid})")
            return True

        except Exception as e:
            logger.error(f"启动 Mihomo 代理失败: {e}")
            self.stop()
            return False

    def _wait_ready(self, timeout: float = 8.0) -> bool:
        """等待 Mihomo external-controller API 就绪

        通过请求 /configs 端点判断 Mihomo 是否已启动完成。
        """
        url = f"http://127.0.0.1:{self.external_controller_port}/configs"
        headers = {"Authorization": f"Bearer {self.secret}"}
        deadline = time.time() + timeout

        while time.time() < deadline:
            if not self.is_running:
                return False
            try:
                resp = httpx.get(url, headers=headers, timeout=1.0)
                if resp.status_code in (200, 304):
                    return True
            except Exception:
                pass
            time.sleep(0.3)

        return False

    def stop(self) -> None:
        """停止 Mihomo 进程并清理临时文件（幂等）"""
        if self._process is not None:
            if self.is_running:
                try:
                    self._process.terminate()
                    self._process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self._process.kill()
                    self._process.wait(timeout=3)
                except Exception:
                    pass
            self._process = None

        self._cleanup_temp()

    def _cleanup_temp(self) -> None:
        """清理临时目录（仅删除 tmp_browser_ 开头的目录）"""
        if self._temp_dir and self._temp_dir.exists():
            if self._temp_dir.name.startswith("tmp_browser_"):
                try:
                    shutil.rmtree(self._temp_dir)
                except Exception:
                    pass
        self._temp_dir = None

    def _build_mihomo_config(self) -> dict:
        """构建仅包含当前节点的 Mihomo 配置"""
        proxy_dict = dict(self.node.clash_proxy)

        # 确保必要字段存在
        if "name" not in proxy_dict:
            proxy_dict["name"] = "BrowserProxy"
        if "type" not in proxy_dict:
            proxy_dict["type"] = self.node.protocol.value

        config = {
            "mixed-port": self.mixed_port,
            "allow-lan": False,
            "bind-address": "127.0.0.1",
            "mode": "global",
            "log-level": "warning",
            "external-controller": f"127.0.0.1:{self.external_controller_port}",
            "secret": self.secret,
            "proxies": [proxy_dict],
            "proxy-groups": [
                {
                    "name": "Proxy",
                    "type": "select",
                    "proxies": [proxy_dict["name"]],
                }
            ],
            "rules": [
                "MATCH,Proxy"
            ],
        }

        return config
