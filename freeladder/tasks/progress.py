# path: freeladder/tasks/progress.py
"""进度节流器

避免 GUI 被大量进度回调淹没。
GUI / CLI 日志和进度都必须使用此节流器。
"""

import time


class ProgressThrottler:
    """进度节流器：限制回调频率"""

    def __init__(self, interval_ms: int = 500):
        self.interval = interval_ms / 1000.0
        self.last_emit = 0.0

    def should_emit(self) -> bool:
        """是否应该发送新的进度更新"""
        now = time.time()
        if now - self.last_emit >= self.interval:
            self.last_emit = now
            return True
        return False

    def reset(self):
        """重置节流器"""
        self.last_emit = 0.0
