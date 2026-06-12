# path: freeladder/tasks/task_manager.py
"""统一任务管理器

同一时间只允许一个重任务运行。
自动向支持 cancel_token / on_progress 的函数注入参数。
异常必须捕获，不能导致 GUI 卡死。
"""

import inspect
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from typing import Callable, Optional

from loguru import logger

from freeladder.core.cancel_token import CancelToken
from .task_models import ManagedTask, TaskStatus, TaskResult


class TaskManager:
    """统一任务管理器

    保证:
    - 同一时间只允许一个重任务运行
    - 自动注入 cancel_token / on_progress
    - 异常捕获，finally 恢复状态
    """

    def __init__(self, max_workers: int = 2):
        self._executor = ThreadPoolExecutor(
            max_workers=max_workers, thread_name_prefix="task-manager"
        )
        self._lock = threading.Lock()
        self._current_task: Optional[ManagedTask] = None
        self._current_token: Optional[CancelToken] = None

    def has_running_task(self) -> bool:
        """是否有正在运行的任务"""
        with self._lock:
            return (
                self._current_task is not None
                and self._current_task.status == TaskStatus.RUNNING
            )

    def get_current_task(self) -> Optional[ManagedTask]:
        """获取当前任务"""
        with self._lock:
            return self._current_task

    def start_task(
        self,
        name: str,
        func: Callable,
        on_progress: Optional[Callable] = None,
        on_done: Optional[Callable] = None,
        **kwargs,
    ) -> Optional[ManagedTask]:
        """启动后台任务

        如果已有 RUNNING 任务则拒绝。
        func 支持 cancel_token / on_progress 时自动注入。
        """
        with self._lock:
            if self._current_task and self._current_task.status == TaskStatus.RUNNING:
                logger.warning(f"已有任务在运行，拒绝新任务: {name}")
                return None

            task = ManagedTask(
                task_id=str(uuid.uuid4())[:8],
                name=name,
                status=TaskStatus.RUNNING,
                started_at=time.time(),
            )
            token = CancelToken()
            self._current_task = task
            self._current_token = token

        def _worker():
            try:
                sig = inspect.signature(func)
                params = sig.parameters

                inject_kwargs = dict(kwargs)
                if "cancel_token" in params:
                    inject_kwargs["cancel_token"] = token
                if "on_progress" in params:
                    inject_kwargs["on_progress"] = on_progress

                result = func(**inject_kwargs)

                with self._lock:
                    task.status = TaskStatus.DONE
                    task.finished_at = time.time()

                if on_done:
                    if isinstance(result, TaskResult):
                        on_done(result)
                    elif isinstance(result, dict):
                        on_done(TaskResult(ok=True, message="done", data=result))
                    else:
                        on_done(result)

            except CancelToken.CancelledError:
                logger.info(f"任务已取消: {name}")
                with self._lock:
                    task.status = TaskStatus.CANCELLED
                    task.finished_at = time.time()
                if on_done:
                    on_done(TaskResult(ok=False, message="cancelled"))

            except Exception as e:
                logger.error(f"任务异常 {name}: {e}")
                with self._lock:
                    task.status = TaskStatus.FAILED
                    task.error = str(e)[:500]
                    task.finished_at = time.time()
                if on_done:
                    on_done(TaskResult(ok=False, message=str(e)))

            finally:
                with self._lock:
                    if self._current_task is task:
                        self._current_task = None
                        self._current_token = None

        self._executor.submit(_worker)
        return task

    def cancel_current(self) -> bool:
        """取消当前任务"""
        with self._lock:
            if (
                self._current_task
                and self._current_task.status == TaskStatus.RUNNING
                and self._current_token
            ):
                self._current_task.status = TaskStatus.CANCELLING
                self._current_token.cancel()
                logger.info(f"已请求取消任务: {self._current_task.name}")
                return True
            return False

    def shutdown(self, wait: bool = True):
        """关闭任务管理器"""
        self.cancel_current()
        self._executor.shutdown(wait=wait)
