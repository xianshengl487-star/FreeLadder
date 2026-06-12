# path: tests/test_database_wal_indexes.py
"""测试数据库 WAL 和索引

覆盖:
- SQLite WAL 初始化不会报错
- 索引创建不会报错
- busy_timeout 设置
- synchronous 设置
"""

import pytest
from freeladder.core.database import Database


class TestDatabaseWALIndexes:
    def test_wal_mode_enabled(self, tmp_path):
        db = Database(str(tmp_path / "test.db"))
        result = db._conn.execute("PRAGMA journal_mode").fetchone()
        assert result[0].lower() == "wal"

    def test_synchronous_normal(self, tmp_path):
        db = Database(str(tmp_path / "test.db"))
        result = db._conn.execute("PRAGMA synchronous").fetchone()
        # NORMAL = 1
        assert result[0] == 1

    def test_temp_store_memory(self, tmp_path):
        db = Database(str(tmp_path / "test.db"))
        result = db._conn.execute("PRAGMA temp_store").fetchone()
        # MEMORY = 2
        assert result[0] == 2

    def test_busy_timeout_set(self, tmp_path):
        db = Database(str(tmp_path / "test.db"))
        result = db._conn.execute("PRAGMA busy_timeout").fetchone()
        assert result[0] == 5000

    def test_indexes_exist(self, tmp_path):
        db = Database(str(tmp_path / "test.db"))
        indexes = db._conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND name LIKE 'idx_nodes_%'"
        ).fetchall()
        index_names = {row[0] for row in indexes}
        expected = {
            "idx_nodes_node_key",
            "idx_nodes_alive",
            "idx_nodes_score",
            "idx_nodes_protocol",
            "idx_nodes_country",
            "idx_nodes_last_checked",
        }
        assert expected.issubset(index_names)

    def test_double_init_no_error(self, tmp_path):
        """重复初始化不会报错"""
        db = Database(str(tmp_path / "test.db"))
        db._init_tables()
        db._create_indexes()

    def test_wal_does_not_break_write(self, tmp_path):
        """WAL 模式下写入正常"""
        from freeladder.core.models import Node, Protocol
        db = Database(str(tmp_path / "test.db"))
        node = Node(
            node_key="vmess:wal_test:443",
            protocol=Protocol.VMESS,
            server="1.2.3.4",
            port=443,
            name="WAL Test",
        )
        db.upsert_node(node)
        assert db.get_node_count() == 1
