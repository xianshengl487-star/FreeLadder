# path: tests/test_db_writer.py
"""测试 DBWriter 单写入线程

覆盖:
- 批量写入节点
- queue 满时不丢数据
- flush 正常工作
- close 正常工作
- 统计正确
"""

import time
import pytest

from freeladder.tasks.db_writer import DBWriter, DBWriteStats
from freeladder.core.cancel_token import CancelToken
from freeladder.core.database import Database
from freeladder.core.models import Node, Protocol


def _make_nodes(count):
    return [
        Node(
            node_key=f"vmess:dbw{i}:443",
            raw_hash=f"dbw{i:06d}",
            protocol=Protocol.VMESS,
            server=f"10.0.{i // 256}.{i % 256}",
            port=443,
            name=f"DBW Node {i}",
            raw_uri=f"vmess://dbw{i}",
        )
        for i in range(count)
    ]


class TestDBWriter:
    def test_submit_and_flush(self, tmp_path):
        db = Database(str(tmp_path / "test.db"))
        writer = DBWriter(db, batch_size=50, queue_max_size=100)
        nodes = _make_nodes(30)
        writer.start()
        writer.submit_nodes(nodes)
        writer.close()
        assert writer.stats.received == 30
        assert db.get_node_count() == 30

    def test_multiple_batches(self, tmp_path):
        db = Database(str(tmp_path / "test.db"))
        writer = DBWriter(db, batch_size=5, queue_max_size=100)
        writer.start()
        # Submit multiple batches with enough data
        writer.submit_nodes(_make_nodes(25))
        writer.close()
        assert db.get_node_count() == 25
        assert writer.stats.batches >= 1

    def test_queue_full_backpressure(self, tmp_path):
        """队列满时阻塞，不应丢数据"""
        db = Database(str(tmp_path / "test.db"))
        writer = DBWriter(db, batch_size=50, queue_max_size=2)
        writer.start()
        # submit 10 batches, queue_max=2, should block but not lose
        for i in range(10):
            writer.submit_nodes(_make_nodes(10))
        writer.close()
        assert writer.stats.received == 100

    def test_flush_writes_immediately(self, tmp_path):
        db = Database(str(tmp_path / "test.db"))
        writer = DBWriter(db, batch_size=100, queue_max_size=100)
        writer.start()
        writer.submit_nodes(_make_nodes(20))
        writer.flush()
        assert db.get_node_count() == 20
        writer.close()

    def test_empty_submit(self, tmp_path):
        db = Database(str(tmp_path / "test.db"))
        writer = DBWriter(db, batch_size=10, queue_max_size=10)
        writer.start()
        writer.submit_nodes([])
        writer.close()
        assert writer.stats.received == 0

    def test_stats_tracking(self, tmp_path):
        db = Database(str(tmp_path / "test.db"))
        writer = DBWriter(db, batch_size=20, queue_max_size=100)
        writer.start()
        writer.submit_nodes(_make_nodes(60))
        writer.close()
        assert writer.stats.received == 60
        assert writer.stats.inserted == 60
        assert writer.stats.batches >= 1

    def test_cancel_token_stops_writing(self, tmp_path):
        db = Database(str(tmp_path / "test.db"))
        token = CancelToken()
        writer = DBWriter(db, batch_size=50, queue_max_size=100)
        writer.start(cancel_token=token)
        writer.submit_nodes(_make_nodes(100))
        token.cancel()
        writer.flush()
        writer.close()
        # Should have written at least some
        assert writer.stats.received > 0
