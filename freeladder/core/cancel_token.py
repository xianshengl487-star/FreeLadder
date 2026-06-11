"""线程安全的取消令牌

用于在后台任务中支持取消操作。
"""

import threading


class CancelToken:
    """线程安全的取消令牌

    使用 threading.Event 实现，支持:
    - cancel(): 设置取消标志
    - cancelled: 检查是否已取消
    - raise_if_cancelled(): 已取消时抛出 CancelledError
    """

    class CancelledError(Exception):
        """任务已被取消"""
        pass

    def __init__(self):
        self._event = threading.Event()

    def cancel(self):
        """设置取消标志"""
        self._event.set()

    @property
    def cancelled(self) -> bool:
        """是否已取消"""
        return self._event.is_set()

    def raise_if_cancelled(self):
        """如果已取消则抛出 CancelledError"""
        if self.cancelled:
            raise self.CancelledError("任务已被取消")

    def wait(self, timeout: float = None) -> bool:
        """等待取消事件，返回是否被取消"""
        return self._event.wait(timeout=timeout)
