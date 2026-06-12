# path: freeladder/tasks/db_writer.py
"""单写入线程 DBWriter

避免 SQLite 多线程写入导致 database is locked。
使用 Queue(maxsize) 实现 backpressure。

工作流程:
1. 爬取/测试线程调用 submit_nodes(nodes) 放入队列
2. 单独的写入线程从队列取出节点批次
3. 每 batch_size 条调用 db.upsert_nodes_bulk 写入一次
4. 支持 cancel_token、flush、close、wait
"""

import queue
import threading
import time
from dataclasses import dataclass, field
from typing import Optional

from loguru import logger

from freeladder.core.cancel_token import CancelToken


@dataclass
class DBWriteStats:
    """DB 写入统计"""
    received: int = 0
    inserted: int = 0
    updated: int = 0
    batches: int = 0
    queue_peak: int = 0


class DBWriter:
    """单写入线程 DBWriter"""

    def __init__(self, db, batch_size: int = 500, queue_max_size: int = 3000):
        self.db = db
        self.batch_size = batch_size
        self._queue_max = queue_max_size
        self._queue: queue.Queue = queue.Queue(maxsize=queue_max_size)
        self.stats = DBWriteStats()
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._flush_event = threading.Event()
        self._done_event = threading.Event()
        self._lock = threading.Lock()

    def start(self, on_progress=None, cancel_token=None):
        """启动写入线程"""
        self._stop_event.clear()
        self._done_event.clear()
        self._thread = threading.Thread(
            target=self._write_loop,
            args=(on_progress, cancel_token),
            daemon=True,
            name="db-writer",
        )
        self._thread.start()

    def submit_nodes(self, nodes: list):
        """提交节点到写入队列

        队列满时阻塞等待（backpressure）。
        """
        if not nodes:
            return
        with self._lock:
            self.stats.received += len(nodes)
            peak = self._queue.qsize()
            if peak > self.stats.queue_peak:
                self.stats.queue_peak = peak

        try:
            self._queue.put(nodes, timeout=30)
        except queue.Full:
            logger.warning("DBWriter 队列满，丢弃本批次")
            with self._lock:
                self.stats.received -= len(nodes)

    def close(self):
        """通知停止并排空队列"""
        self._stop_event.set()
        # 放入哨兵，唤醒阻塞的 get
        try:
            self._queue.put(None, timeout=1)
        except queue.Full:
            pass
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=30)

    def flush(self):
        """触发一次立即排空"""
        self._flush_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=15)

    def wait(self, timeout: float = None):
        """等待写入完成"""
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=timeout)

    def _write_loop(self, on_progress=None, cancel_token=None):
        """写入主循环"""
        batch = []
        try:
            while not self._stop_event.is_set():
                if cancel_token and cancel_token.cancelled:
                    break

                try:
                    item = self._queue.get(timeout=1.0)
                except queue.Empty:
                    # 超时，处理已有批次
                    if batch:
                        self._flush_batch(batch, cancel_token)
                        batch = []
                    continue

                if item is None:
                    # 哨兵，退出
                    break

                batch.extend(item)

                # 达到 batch_size 或 flush 信号
                if len(batch) >= self.batch_size or self._flush_event.is_set():
                    self._flush_event.clear()
                    self._flush_batch(batch, cancel_token)
                    batch = []

                # Also flush small batches when queue is caught up (no more pending)
                elif len(batch) > 0 and self._queue.empty() and not self._stop_event.is_set():
                    # Small delay to allow more items to arrive
                    time.sleep(0.01)
                    if self._queue.empty() and len(batch) > 0:
                        self._flush_batch(batch, cancel_token)
                        batch = []

                if on_progress:
                    on_progress(self.stats.received, self.stats.inserted + self.stats.updated, "DB写入中")

            # 排空剩余
            while not self._queue.empty():
                try:
                    item = self._queue.get_nowait()
                    if item is not None:
                        batch.extend(item)
                except queue.Empty:
                    break

            if batch:
                self._flush_batch(batch, cancel_token)

            self._done_event.set()

        except Exception as e:
            logger.error(f"DBWriter 写入循环异常: {e}")
            self._done_event.set()

    def _flush_batch(self, nodes: list, cancel_token=None):
        """写入一批节点"""
        if not nodes:
            return
        try:
            added = self.db.upsert_nodes_bulk(
                nodes, batch_size=self.batch_size, cancel_token=cancel_token
            )
            with self._lock:
                self.stats.batches += 1
                self.stats.inserted += added
                self.stats.updated += len(nodes) - added
            logger.debug(f"DBWriter 批次 {self.stats.batches}: 写入 {len(nodes)} 个节点，新增 {added}")
        except Exception as e:
            logger.error(f"DBWriter 批次写入失败: {e}")
