# path: freeladder/tasks/task_models.py
"""任务数据模型"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class TaskStatus(str, Enum):
    """任务状态"""
    PENDING = "pending"
    RUNNING = "running"
    CANCELLING = "cancelling"
    CANCELLED = "cancelled"
    DONE = "done"
    FAILED = "failed"


@dataclass
class TaskProgress:
    """任务进度"""
    current: int = 0
    total: int = 0
    message: str = ""
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class TaskResult:
    """任务结果"""
    ok: bool
    message: str = ""
    data: dict[str, Any] = field(default_factory=dict)


@dataclass
class ManagedTask:
    """受管理的任务"""
    task_id: str
    name: str
    status: TaskStatus = TaskStatus.PENDING
    progress: TaskProgress = field(default_factory=TaskProgress)
    started_at: float = 0.0
    finished_at: float = 0.0
    error: str = ""
