# path: freeladder/source_intel/scheduler.py
"""源情报引擎调度器

后台调度 GitHub 源监控、非 GitHub 源发现、RSS 监控。
默认不自动抓节点，只刷新源候选状态。
"""

import threading
import time
from typing import Optional

from loguru import logger

from .engine import SourceIntelEngine


class SourceIntelScheduler:
    """源情报引擎调度器"""

    def __init__(self, engine: SourceIntelEngine, config=None):
        if config is None:
            from freeladder.core.config import get_config
            config = get_config().source_intel
        self._engine = engine
        self._config = config
        self._thread: Optional[threading.Thread] = None
        self._running = False
        self._last_github_check = 0.0
        self._last_non_github_check = 0.0
        self._last_rss_check = 0.0

    def start(self) -> None:
        """启动调度器"""
        if self._running:
            return

        self._running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        logger.info("源情报调度器已启动")

    def stop(self) -> None:
        """停止调度器"""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
            self._thread = None
        logger.info("源情报调度器已停止")

    def run_once(self) -> dict:
        """手动执行一次刷新"""
        results = {"github": 0, "non_github": 0, "rss": 0}

        if self.should_run_github_check():
            sources = self._engine.discover_github_sources()
            results["github"] = len(sources)
            self._last_github_check = time.time()

        if self.should_run_non_github_check():
            sources = self._engine.discover_non_github_sources()
            results["non_github"] = len(sources)
            self._last_non_github_check = time.time()

        if self.should_run_rss_check():
            sources = self._engine._discover_rss_sources()
            results["rss"] = len(sources)
            self._last_rss_check = time.time()

        return results

    def _run_loop(self) -> None:
        """调度循环"""
        while self._running:
            try:
                if self.should_run_github_check():
                    sources = self._engine.discover_github_sources()
                    self._last_github_check = time.time()
                    logger.info(f"GitHub 源刷新: {len(sources)} 个候选")

                if self.should_run_non_github_check():
                    sources = self._engine.discover_non_github_sources()
                    self._last_non_github_check = time.time()
                    logger.info(f"非 GitHub 源刷新: {len(sources)} 个候选")

                if self.should_run_rss_check():
                    sources = self._engine._discover_rss_sources()
                    self._last_rss_check = time.time()
                    logger.info(f"RSS 源刷新: {len(sources)} 个候选")

            except Exception as e:
                logger.error(f"源情报调度异常: {e}")

            # 每 60 秒检查一次是否需要执行
            time.sleep(60)

    def should_run_github_check(self) -> bool:
        """是否应该执行 GitHub 检查"""
        if not self._config.github_watch_enabled:
            return False
        interval = self._config.github_check_interval_minutes * 60
        return (time.time() - self._last_github_check) >= interval

    def should_run_non_github_check(self) -> bool:
        """是否应该执行非 GitHub 检查"""
        if not self._config.non_github_discovery_enabled:
            return False
        interval = self._config.non_github_check_interval_minutes * 60
        return (time.time() - self._last_non_github_check) >= interval

    def should_run_rss_check(self) -> bool:
        """是否应该执行 RSS 检查"""
        if not self._config.rss_watch_enabled:
            return False
        interval = self._config.rss_check_interval_minutes * 60
        return (time.time() - self._last_rss_check) >= interval
