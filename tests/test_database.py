# path: tests/test_database.py
"""测试 SQLite 数据库模块"""

import json
import pytest

from freeladder.core.database import Database
from freeladder.core.models import Node, Protocol, TestResult
from tests.conftest import make_node


@pytest.fixture
def db(tmp_path):
    """创建临时 SQLite 数据库"""
    db_path = str(tmp_path / "test.db")
    database = Database(db_path)
    yield database
    database.close()


class TestUpsertNode:

    def test_insert_new_node(self, db):
        node = make_node(protocol=Protocol.HTTP, server="1.2.3.4", port=80)
        node_id = db.upsert_node(node)
        assert node_id is not None
        assert node_id > 0

    def test_upsert_updates_existing(self, db):
        node = make_node(protocol=Protocol.HTTP, server="1.2.3.4", port=80)
        id1 = db.upsert_node(node)

        node.name = "Updated Name"
        id2 = db.upsert_node(node)
        assert id1 == id2

        retrieved = db.get_node_by_key(node.node_key)
        assert retrieved.name == "Updated Name"

    def test_upsert_preserves_counts(self, db):
        node = make_node(protocol=Protocol.HTTP, server="1.2.3.4", port=80)
        db.upsert_node(node)

        # Simulate some test results
        result = TestResult(
            node_id=node.id or 1,
            node_key=node.node_key,
            alive=True,
            latency=100,
            test_mode="basic",
        )
        db.update_test_result(result)

        # Update node but preserve counts
        node.name = "Updated"
        db.upsert_node(node)

        retrieved = db.get_node_by_key(node.node_key)
        assert retrieved.success_count == 1


class TestUpsertNodes:

    def test_batch_insert(self, db):
        nodes = [
            make_node(protocol=Protocol.HTTP, server="1.2.3.4", port=80),
            make_node(protocol=Protocol.SOCKS5, server="5.6.7.8", port=1080),
            make_node(protocol=Protocol.HTTP, server="9.9.9.9", port=80),
        ]
        count = db.upsert_nodes(nodes)
        assert count == 3

    def test_batch_with_duplicates(self, db):
        nodes = [
            make_node(protocol=Protocol.HTTP, server="1.2.3.4", port=80),
            make_node(protocol=Protocol.HTTP, server="1.2.3.4", port=80),
        ]
        count = db.upsert_nodes(nodes)
        assert count == 1  # second is an update


class TestGetNodes:

    def test_get_all_nodes(self, db):
        db.upsert_node(make_node(protocol=Protocol.HTTP, server="1.1.1.1", port=80))
        db.upsert_node(make_node(protocol=Protocol.SOCKS5, server="2.2.2.2", port=1080))
        all_nodes = db.get_all_nodes()
        assert len(all_nodes) == 2

    def test_get_alive_nodes(self, db):
        n1 = make_node(protocol=Protocol.HTTP, server="1.1.1.1", port=80, alive=True)
        n2 = make_node(protocol=Protocol.HTTP, server="2.2.2.2", port=80, alive=False)
        db.upsert_node(n1)
        db.upsert_node(n2)
        alive = db.get_alive_nodes()
        assert len(alive) == 1
        assert alive[0].server == "1.1.1.1"

    def test_get_nodes_by_protocol(self, db):
        db.upsert_node(make_node(protocol=Protocol.HTTP, server="1.1.1.1", port=80))
        db.upsert_node(make_node(protocol=Protocol.SOCKS5, server="2.2.2.2", port=1080))
        http_nodes = db.get_nodes_by_protocol("http")
        assert len(http_nodes) == 1

    def test_get_nodes_by_country(self, db):
        db.upsert_node(make_node(protocol=Protocol.HTTP, server="1.1.1.1", port=80, country="US"))
        db.upsert_node(make_node(protocol=Protocol.HTTP, server="2.2.2.2", port=80, country="JP"))
        us_nodes = db.get_nodes_by_country("US")
        assert len(us_nodes) == 1

    def test_get_node_by_key_not_found(self, db):
        assert db.get_node_by_key("nonexistent") is None


class TestUpdateTestResult:

    def test_alive_result(self, db):
        node = make_node(protocol=Protocol.HTTP, server="1.2.3.4", port=80)
        db.upsert_node(node)

        result = TestResult(
            node_id=node.id,
            node_key=node.node_key,
            alive=True,
            latency=150,
            test_mode="basic",
        )
        db.update_test_result(result)

        updated = db.get_node_by_key(node.node_key)
        assert updated.alive is True
        assert updated.latency == 150
        assert updated.success_count == 1
        assert updated.fail_count == 0

    def test_dead_result(self, db):
        node = make_node(protocol=Protocol.HTTP, server="1.2.3.4", port=80)
        db.upsert_node(node)

        result = TestResult(
            node_id=node.id,
            node_key=node.node_key,
            alive=False,
            error="Connection refused",
            test_mode="basic",
        )
        db.update_test_result(result)

        updated = db.get_node_by_key(node.node_key)
        assert updated.alive is False
        assert updated.fail_count == 1
        assert updated.last_error == "Connection refused"

    def test_alive_clears_fail_count(self, db):
        node = make_node(protocol=Protocol.HTTP, server="1.2.3.4", port=80, fail_count=5)
        db.upsert_node(node)

        result = TestResult(
            node_id=node.id,
            node_key=node.node_key,
            alive=True,
            latency=100,
            test_mode="basic",
        )
        db.update_test_result(result)

        updated = db.get_node_by_key(node.node_key)
        assert updated.fail_count == 0
        assert updated.success_count == 1

    def test_avg_latency_ema(self, db):
        node = make_node(protocol=Protocol.HTTP, server="1.2.3.4", port=80)
        db.upsert_node(node)

        # First test
        r1 = TestResult(node_id=node.id, node_key=node.node_key, alive=True, latency=100, test_mode="basic")
        db.update_test_result(r1)
        updated = db.get_node_by_key(node.node_key)
        assert updated.avg_latency == 100.0

        # Second test: EMA = 100 * 0.7 + 200 * 0.3 = 130
        r2 = TestResult(node_id=node.id, node_key=node.node_key, alive=True, latency=200, test_mode="basic")
        db.update_test_result(r2)
        updated = db.get_node_by_key(node.node_key)
        assert updated.avg_latency == pytest.approx(130.0, abs=0.1)

    def test_score_is_updated(self, db):
        node = make_node(protocol=Protocol.HTTP, server="1.2.3.4", port=80)
        db.upsert_node(node)

        result = TestResult(
            node_id=node.id, node_key=node.node_key,
            alive=True, latency=100, test_mode="basic",
        )
        db.update_test_result(result)

        updated = db.get_node_by_key(node.node_key)
        assert updated.score > 0
        assert updated.signal != ""


class TestDeleteNodes:

    def test_delete_node(self, db):
        node = make_node(protocol=Protocol.HTTP, server="1.2.3.4", port=80)
        db.upsert_node(node)
        assert db.delete_node(node.id)
        assert db.get_node_by_key(node.node_key) is None

    def test_delete_dead_nodes(self, db):
        n1 = make_node(protocol=Protocol.HTTP, server="1.1.1.1", port=80, fail_count=15)
        n2 = make_node(protocol=Protocol.HTTP, server="2.2.2.2", port=80, fail_count=3)
        db.upsert_node(n1)
        db.upsert_node(n2)

        deleted = db.delete_dead_nodes(max_fail_count=10)
        assert deleted == 1
        assert db.get_node_by_key(n1.node_key) is None
        assert db.get_node_by_key(n2.node_key) is not None


class TestGetStats:

    def test_stats_empty(self, db):
        stats = db.get_stats()
        assert stats["total"] == 0
        assert stats["alive"] == 0

    def test_stats_with_nodes(self, db):
        db.upsert_node(make_node(protocol=Protocol.HTTP, server="1.1.1.1", port=80, alive=True, country="US"))
        db.upsert_node(make_node(protocol=Protocol.SOCKS5, server="2.2.2.2", port=1080, alive=False, country="JP"))
        stats = db.get_stats()
        assert stats["total"] == 2
        assert stats["alive"] == 1
        assert stats["dead"] == 1
        assert "http" in stats["by_protocol"]
        assert stats["by_protocol"]["http"] == 1


class TestGetTestableNodes:

    def test_untested_nodes_are_testable(self, db):
        node = make_node(protocol=Protocol.HTTP, server="1.2.3.4", port=80)
        db.upsert_node(node)
        testable = db.get_testable_nodes()
        assert len(testable) == 1

    def test_recently_tested_not_testable(self, db):
        node = make_node(protocol=Protocol.HTTP, server="1.2.3.4", port=80)
        db.upsert_node(node)
        result = TestResult(
            node_id=node.id, node_key=node.node_key,
            alive=True, latency=100, test_mode="basic",
        )
        db.update_test_result(result)
        testable = db.get_testable_nodes()
        assert len(testable) == 0


class TestContextManager:

    def test_context_manager(self, tmp_path):
        db_path = str(tmp_path / "ctx.db")
        with Database(db_path) as database:
            database.upsert_node(make_node(protocol=Protocol.HTTP, server="1.2.3.4", port=80))
            assert len(database.get_all_nodes()) == 1


class TestClashProxyJson:

    def test_clash_proxy_serialization(self, db):
        proxy = {"name": "test", "type": "vmess", "server": "1.2.3.4", "port": 443, "uuid": "abc"}
        node = make_node(
            protocol=Protocol.VMESS, server="1.2.3.4", port=443,
            clash_proxy=proxy,
        )
        db.upsert_node(node)
        retrieved = db.get_node_by_key(node.node_key)
        assert retrieved.clash_proxy == proxy

    def test_null_clash_proxy(self, db):
        node = make_node(protocol=Protocol.HTTP, server="1.2.3.4", port=80, clash_proxy=None)
        db.upsert_node(node)
        retrieved = db.get_node_by_key(node.node_key)
        assert retrieved.clash_proxy is None
