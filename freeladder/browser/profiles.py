# path: freeladder/browser/profiles.py
"""浏览器 Profile 管理

为每个节点创建独立的 Chromium user data 目录，
实现浏览器数据隔离。
"""

import shutil
from pathlib import Path
from typing import Optional

from loguru import logger


class BrowserProfile:
    """管理单个浏览器 profile 目录"""

    def __init__(self, base_dir: str, node_key: str):
        self._base_dir = Path(base_dir)
        self._node_key = node_key
        self._profile_dir: Optional[Path] = None

    @property
    def profile_path(self) -> Path:
        """获取 profile 目录路径"""
        if self._profile_dir is None:
            # 用 node_key 的前 16 个字符作为目录名，避免特殊字符
            safe_name = self._node_key.replace(":", "_").replace("/", "_")[:16]
            self._profile_dir = self._base_dir / safe_name
        return self._profile_dir

    def create(self) -> Path:
        """创建 profile 目录"""
        self.profile_path.mkdir(parents=True, exist_ok=True)
        logger.debug(f"Browser profile created: {self.profile_path}")
        return self.profile_path

    def remove(self) -> None:
        """删除 profile 目录"""
        if self._profile_dir and self._profile_dir.exists():
            try:
                shutil.rmtree(self._profile_dir)
                logger.debug(f"Browser profile removed: {self._profile_dir}")
            except Exception as e:
                logger.warning(f"Failed to remove browser profile {self._profile_dir}: {e}")

    def __enter__(self):
        self.create()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.remove()
        return False
