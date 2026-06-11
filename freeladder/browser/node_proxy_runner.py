# path: freeladder/browser/node_proxy_runner.py
"""节点代理运行器

为单个 Node 启动临时 Mihomo 实例，提供隔离代理。
每个 NodeProxySession 绑定一个随机 mixed-port，
仅监听 127.0.0.1，不影响系统其他软件。
"""

import json
import os
import subprocess
import time
import secrets
from pathlib import Path
from typing import Optional

import yaml
from loguru import logger

from freeladder.core.config import get_config
from freeladder.core.models import Node, ADVANCED_PROTOCOLS
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
        self._config_path: Optional[Path] = None

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

        # 创建临时目录
        self._temp_dir = Path(f"data/tmp_browser_{os.getpid()}_{self.mixed_port}")
        self._temp_dir.mkdir(parents=True, exist_ok=True)

        # 生成配置
        config = self._build_mihomo_config()
        self._config_path = self._temp_dir / "config.yaml"
        with open(self._config_path, "w", encoding="utf-8") as f:
            yaml.dump(config, f, default_flow_style=False, allow_unicode=True)

        # 启动进程
        try:
            cmd = [
                str(mihomo_path),
                "-d", str(self._temp_dir),
                "-f", str(self._config_path),
            ]
            self._process = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )

            # 等待启动
            time.sleep(1.0)

            if not self.is_running:
                logger.error(f"Mihomo 启动失败，进程已退出")
                self.cleanup()
                return False

            logger.info(f"Mihomo 代理已启动: {self.proxy_url} (PID={self._process.pid})")
            return True

        except Exception as e:
            logger.error(f"启动 Mihomo 失败: {e}")
            self.cleanup()
            return False

    def stop(self) -> None:
        """停止 Mihomo 进程并清理临时文件"""
        if self._process and self.is_running:
            try:
                self._process.terminate()
                self._process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._process.kill()
                self._process.wait(timeout=3)
            except Exception as e:
                logger.warning(f"停止 Mihomo 进程异常: {e}")

        self._process = None
        self.cleanup()

    def cleanup(self) -> None:
        """清理临时目录"""
        if self._temp_dir and self._temp_dir.exists():
            try:
                import shutil
                shutil.rmtree(self._temp_dir)
            except Exception as e:
                logger.warning(f"清理临时目录失败: {e}")
        self._temp_dir = None
        self._config_path = None

    def _build_mihomo_config(self) -> dict:
        """构建仅包含当前节点的 Mihomo 配置"""
        import yaml

        proxy_dict = dict(self.node.clash_proxy)

        # 确保 name 和 type 存在
        if "name" not in proxy_dict:
            proxy_dict["name"] = "BrowserProxy"
        if "type" not in proxy_dict:
            proxy_dict["type"] = self.node.protocol.value

        # 确保 server 和 port 正确
        proxy_dict["server"] = self.node.server
        proxy_dict["port"] = self.node.port

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
                    "name": "BrowserProxy",
                    "type": "select",
                    "proxies": [proxy_dict["name"]],
                }
            ],
            "rules": [
                "MATCH,BrowserProxy"
            ],
        }

        return config
