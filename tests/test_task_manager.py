# path: tests/test_task_manager.py
"""测试 TaskManager

覆盖:
- 同时只允许一个任务
- cancel_current 生效
- 异常捕获不卡死
- 自动注入 cancel_token
- finally 恢复状态
"""

import time
import pytest
from unittest.mock import MagicMock

from freeladder.tasks.task_manager import TaskManager
from freeladder.tasks.task_models import TaskStatus, TaskResult


class TestTaskManager:
    def test_has_running_task_false(self):
        tm = TaskManager()
        assert tm.has_running_task() is False

    def test_start_task_returns_managed_task(self):
        tm = TaskManager()
        task = tm.start_task("test", lambda: "ok")
        assert task is not None
        assert task.name == "test"
        tm.shutdown(wait=True)

    def test_concurrent_task_rejected(self):
        tm = TaskManager()
        task1 = tm.start_task("slow", lambda on_progress=None, cancel_token=None: time.sleep(5))
        time.sleep(0.1)
        assert tm.has_running_task() is True
        task2 = tm.start_task("rejected", lambda: "nope")
        assert task2 is None
        tm.cancel_current()
        tm.shutdown(wait=True)

    def test_cancel_current_sets_token(self):
        tm = TaskManager()
        task = tm.start_task("cancelable", lambda on_progress=None, cancel_token=None: time.sleep(10))
        time.sleep(0.05)
        result = tm.cancel_current()
        assert result is True
        tm.shutdown(wait=True)

    def test_cancel_returns_false_when_no_task(self):
        tm = TaskManager()
        assert tm.cancel_current() is False
        tm.shutdown(wait=True)

    def test_task_done_on_complete(self):
        tm = TaskManager()
        task = tm.start_task("quick", lambda: "done")
        tm.shutdown(wait=True)
        assert task.status == TaskStatus.DONE

    def test_task_failed_on_exception(self):
        tm = TaskManager()
        task = tm.start_task("bad", lambda: 1/0)
        tm.shutdown(wait=True)
        assert task.status == TaskStatus.FAILED

    def test_auto_inject_cancel_token(self):
        tm = TaskManager()
        received = []

        def func(cancel_token=None):
            received.append(cancel_token)
            return "ok"

        task = tm.start_task("inject", func)
        tm.shutdown(wait=True)
        assert len(received) == 1
        assert received[0] is not None
        assert task.status == TaskStatus.DONE

    def test_auto_inject_on_progress(self):
        tm = TaskManager()
        received = []

        def func(cancel_token=None, on_progress=None):
            received.append(on_progress)
            return "ok"

        progress_fn = lambda c, t, m: None
        task = tm.start_task("progress", func, on_progress=progress_fn)
        tm.shutdown(wait=True)
        assert len(received) == 1
        assert received[0] is progress_fn

    def test_on_done_callback_called(self):
        tm = TaskManager()
        done_results = []

        def on_done(r):
            done_results.append(r)

        tm.start_task("callback", lambda: "ok", on_done=on_done)
        tm.shutdown(wait=True)
        assert len(done_results) == 1
        assert done_results[0] == "ok"

    def test_on_done_called_on_failure(self):
        tm = TaskManager()
        done_results = []

        def on_done(r):
            done_results.append(r)

        tm.start_task("fail", lambda: 1/0, on_done=on_done)
        tm.shutdown(wait=True)
        assert len(done_results) == 1
        assert isinstance(done_results[0], TaskResult)
        assert done_results[0].ok is False
