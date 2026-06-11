# path: freeladder/gui/worker.py
"""后台任务工作线程模块

支持:
- 后台执行爬取、测试、导出任务
- 进度回调通知 GUI
- 线程安全的状态管理
"""

import threading
from typing import Callable, Optional

from loguru import logger


class WorkerThread:
    """后台任务工作线程"""

    def __init__(self):
        self._thread: Optional[threading.Thread] = None
        self._running = False
        self._progress_callback: Optional[Callable] = None
        self._done_callback: Optional[Callable] = None

    @property
    def is_running(self) -> bool:
        return self._running

    def start(
        self,
        func: Callable,
        *args,
        on_progress: Optional[Callable] = None,
        on_done: Optional[Callable] = None,
        **kwargs,
    ):
        """启动后台任务

        Args:
            func: 要执行的函数
            on_progress: 进度回调 (current, total, message)
            on_done: 完成回调 (result)
        """
        if self._running:
            logger.warning("已有任务在运行中")
            return

        self._running = True
        self._progress_callback = on_progress
        self._done_callback = on_done

        def _worker():
            try:
                result = func(*args, on_progress=self._progress_callback, **kwargs)
                if self._done_callback:
                    self._done_callback(result)
            except Exception as e:
                logger.error(f"后台任务异常: {e}")
                if self._done_callback:
                    self._done_callback(None)
            finally:
                self._running = False

        self._thread = threading.Thread(target=_worker, daemon=True)
        self._thread.start()

    def stop(self):
        """停止任务（仅设置标志，不能强制终止）"""
        self._running = False

    def wait(self, timeout: float = None):
        """等待任务完成"""
        if self._thread:
            self._thread.join(timeout=timeout)
