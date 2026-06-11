# path: freeladder/browser/profiles.py
"""浏览器 Profile 管理

为每个节点创建独立的 Chromium user data 目录，实现浏览器数据隔离。
"""

import shutil
from pathlib import Path
from typing import Optional

from loguru import logger


class BrowserProfile:
    """管理单个浏览器 profile"""

    def __init__(self, base_dir: str, node_key: str):
        self.base_dir = Path(base_dir)
        self.node_key = node_key
        self._path: Optional[Path] = None

    @property
    def profile_path(self) -> Path:
        """profile 目录路径"""
        if self._path is None:
            # 用 node_key 的 hash 前 12 位作为目录名，避免特殊字符
            import hashlib
            safe_name = hashlib.sha256(self.node_key.encode()).hexdigest()[:12]
            self._path = self.base_dir / safe_name
        return self._path

    def create(self) -> Path:
        """创建 profile 目录"""
        self.profile_path.mkdir(parents=True, exist_ok=True)
        logger.debug(f"Browser profile created: {self.profile_path}")
        return self.profile_path

    def remove(self) -> None:
        """删除 profile 目录"""
        if self._path and self._path.exists():
            try:
                shutil.rmtree(self._path)
                logger.debug(f"Browser profile removed: {self._path}")
            except Exception as e:
                logger.warning(f"Failed to remove browser profile: {e}")

    def __enter__(self):
        self.create()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.remove()
        return False
