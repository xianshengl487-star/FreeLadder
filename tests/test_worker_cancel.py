# path: tests/test_worker_cancel.py
"""WorkerThread 取消机制测试"""

import time
from unittest.mock import MagicMock

import pytest

from freeladder.core.cancel_token import CancelToken
from freeladder.gui.worker import WorkerThread


class TestWorkerCancel:
    def test_init(self):
        w = WorkerThread()
        assert w.is_running is False
        assert w.cancel_token is None

    def test_start_creates_cancel_token(self):
        w = WorkerThread()
        result_box = []

        def slow_func(on_progress=None, cancel_token=None):
            result_box.append(cancel_token)
            return "done"

        w.start(slow_func)
        time.sleep(0.1)
        assert w.cancel_token is not None
        w.wait(timeout=2)

    def test_stop_sets_cancel_token(self):
        w = WorkerThread()

        def slow_func(on_progress=None, cancel_token=None):
            time.sleep(10)
            return "done"

        w.start(slow_func)
        time.sleep(0.05)
        w.stop()
        assert w.cancel_token is not None
        assert w.cancel_token.cancelled is True
        assert w.is_running is False

    def test_stop_cancels_running_task(self):
        w = WorkerThread()
        was_cancelled = []

        def checking_func(on_progress=None, cancel_token=None):
            while not cancel_token.cancelled:
                time.sleep(0.01)
            was_cancelled.append(True)
            return "cancelled"

        w.start(checking_func)
        time.sleep(0.1)
        w.stop()
        w.wait(timeout=2)
        assert len(was_cancelled) == 1

    def test_cancel_token_auto_injected(self):
        """如果函数签名有 cancel_token，WorkerThread 自动注入"""
        w = WorkerThread()
        received_tokens = []

        def func_with_token(on_progress=None, cancel_token=None):
            received_tokens.append(cancel_token)
            return "ok"

        w.start(func_with_token)
        w.wait(timeout=2)
        assert len(received_tokens) == 1
        assert received_tokens[0] is w.cancel_token

    def test_compat_old_function(self):
        """兼容没有 cancel_token 参数的旧函数"""
        w = WorkerThread()

        def old_func(on_progress=None):
            return "ok"

        w.start(old_func)
        w.wait(timeout=2)
        assert w.is_running is False

    def test_done_callback_on_cancel(self):
        w = WorkerThread()
        done_results = []

        def cancellable_func(on_progress=None, cancel_token=None):
            # Sleep in small increments, checking cancel_token
            for _ in range(100):
                if cancel_token.cancelled:
                    raise CancelToken.CancelledError()
                time.sleep(0.05)
            return "done"

        w.start(cancellable_func, on_done=lambda r: done_results.append(r))
        time.sleep(0.1)
        w.stop()
        w.wait(timeout=3)
        time.sleep(0.1)
        assert len(done_results) == 1

    def test_second_start_rejected(self):
        w = WorkerThread()

        def slow_func(on_progress=None, cancel_token=None):
            time.sleep(10)
            return "done"

        w.start(slow_func)
        time.sleep(0.05)
        w.start(slow_func)  # Should be rejected
        w.stop()
        w.wait(timeout=2)
