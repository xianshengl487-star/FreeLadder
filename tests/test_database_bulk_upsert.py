# path: tests/test_database_bulk_upsert.py
"""批量入库性能测试

验证 upsert_nodes_bulk 的正确性、性能和取消支持
"""

import pytest

from freeladder.core.cancel_token import CancelToken
from freeladder.core.database import Database
from freeladder.core.models import Node, Protocol


def _make_nodes(count, prefix="vmess"):
    """批量生成测试节点"""
    return [
        Node(
            node_key=f"{prefix}:node{i}:443",
            raw_hash=f"hash{i:06d}",
            protocol=Protocol.VMESS,
            server=f"10.0.{i // 256}.{i % 256}",
            port=443,
            name=f"Node {i}",
            raw_uri=f"{prefix}://test{i}",
            country="US" if i % 3 == 0 else "JP",
        )
        for i in range(count)
    ]


class TestUpsertNodesBulk:
    def test_insert_empty(self, tmp_path):
        db = Database(str(tmp_path / "test.db"))
        count = db.upsert_nodes_bulk([], batch_size=100)
        assert count == 0

    def test_insert_new_nodes(self, tmp_path):
        db = Database(str(tmp_path / "test.db"))
        nodes = _make_nodes(100)
        added = db.upsert_nodes_bulk(nodes, batch_size=50)
        assert added == 100
        total = db.get_node_count()
        assert total == 100

    def test_insert_updates_existing(self, tmp_path):
        db = Database(str(tmp_path / "test.db"))
        nodes1 = _make_nodes(50)
        added1 = db.upsert_nodes_bulk(nodes1, batch_size=50)
        assert added1 == 50

        # Same keys, different names
        nodes2 = _make_nodes(50)
        for n in nodes2:
            n.name = "Updated " + n.name
        added2 = db.upsert_nodes_bulk(nodes2, batch_size=50)
        assert added2 == 0  # No new nodes, just updates

    def test_insert_mixed_new_and_update(self, tmp_path):
        db = Database(str(tmp_path / "test.db"))
        nodes1 = _make_nodes(30)
        db.upsert_nodes_bulk(nodes1, batch_size=50)

        # 30 existing + 20 new
        nodes2 = _make_nodes(50)
        added = db.upsert_nodes_bulk(nodes2, batch_size=50)
        assert added == 20

    def test_batch_size_respected(self, tmp_path):
        db = Database(str(tmp_path / "test.db"))
        nodes = _make_nodes(10)
        added = db.upsert_nodes_bulk(nodes, batch_size=3)
        assert added == 10

    def test_progress_callback(self, tmp_path):
        db = Database(str(tmp_path / "test.db"))
        nodes = _make_nodes(20)
        progress_calls = []

        def on_progress(done, total, msg):
            progress_calls.append((done, total))

        added = db.upsert_nodes_bulk(nodes, batch_size=5, on_progress=on_progress)
        assert added == 20
        assert len(progress_calls) >= 1
        # Last progress should show all done
        assert progress_calls[-1][0] == 20

    def test_cancel_token(self, tmp_path):
        db = Database(str(tmp_path / "test.db"))
        nodes = _make_nodes(100)
        token = CancelToken()

        # Cancel after first batch
        def on_progress(done, total, msg):
            if done >= 10:
                token.cancel()

        added = db.upsert_nodes_bulk(nodes, batch_size=10, cancel_token=token, on_progress=on_progress)
        # Should have inserted some but not all
        assert added < 100

    def test_cancel_before_start(self, tmp_path):
        db = Database(str(tmp_path / "test.db"))
        nodes = _make_nodes(100)
        token = CancelToken()
        token.cancel()

        added = db.upsert_nodes_bulk(nodes, batch_size=10, cancel_token=token)
        assert added == 0

    def test_large_batch(self, tmp_path):
        db = Database(str(tmp_path / "test.db"))
        nodes = _make_nodes(500)
        added = db.upsert_nodes_bulk(nodes, batch_size=100)
        assert added == 500
        total = db.get_node_count()
        assert total == 500

    def test_very_large_batch(self, tmp_path):
        db = Database(str(tmp_path / "test.db"))
        nodes = _make_nodes(2000)
        added = db.upsert_nodes_bulk(nodes, batch_size=500)
        assert added == 2000

    def test_no逐条commit(self, tmp_path):
        """验证不是每条都 commit（通过批量速度间接验证）"""
        db = Database(str(tmp_path / "test.db"))
        nodes = _make_nodes(1000)
        import time
        t0 = time.time()
        db.upsert_nodes_bulk(nodes, batch_size=500)
        elapsed = time.time() - t0
        # Should complete in < 5 seconds even on slow disk
        assert elapsed < 5.0
