# path: tests/test_gui_pagination.py
"""GUI 分页和渲染限制测试

验证:
- get_nodes_page 返回固定数量
- get_node_count 正确
- 筛选条件组合
"""

import pytest

from freeladder.core.database import Database
from freeladder.core.models import Node, Protocol


def _make_nodes(count):
    """批量生成测试节点"""
    return [
        Node(
            node_key=f"vmess:page{i}:443",
            raw_hash=f"ph{i:06d}",
            protocol=Protocol.VMESS,
            server=f"10.0.{i // 256}.{i % 256}",
            port=443,
            name=f"Node {i}",
            raw_uri=f"vmess://test{i}",
            country="US" if i % 3 == 0 else "JP",
            alive=(i % 5 == 0),
            score=float(100 - i),
        )
        for i in range(count)
    ]


class TestGetNodesPage:
    def test_empty_db(self, tmp_path):
        db = Database(str(tmp_path / "test.db"))
        nodes = db.get_nodes_page(offset=0, limit=200)
        assert nodes == []

    def test_first_page(self, tmp_path):
        db = Database(str(tmp_path / "test.db"))
        nodes = _make_nodes(100)
        db.upsert_nodes_bulk(nodes, batch_size=100)

        page = db.get_nodes_page(offset=0, limit=20)
        assert len(page) == 20

    def test_second_page(self, tmp_path):
        db = Database(str(tmp_path / "test.db"))
        nodes = _make_nodes(100)
        db.upsert_nodes_bulk(nodes, batch_size=100)

        page = db.get_nodes_page(offset=20, limit=20)
        assert len(page) == 20
        # First node of page 2 should differ from page 1
        page1 = db.get_nodes_page(offset=0, limit=20)
        assert page[0].node_key != page1[0].node_key

    def test_last_page_partial(self, tmp_path):
        db = Database(str(tmp_path / "test.db"))
        nodes = _make_nodes(50)
        db.upsert_nodes_bulk(nodes, batch_size=50)

        page = db.get_nodes_page(offset=40, limit=20)
        assert len(page) == 10

    def test_offset_beyond_total(self, tmp_path):
        db = Database(str(tmp_path / "test.db"))
        nodes = _make_nodes(10)
        db.upsert_nodes_bulk(nodes, batch_size=10)

        page = db.get_nodes_page(offset=100, limit=20)
        assert page == []

    def test_filter_protocol(self, tmp_path):
        db = Database(str(tmp_path / "test.db"))
        nodes = _make_nodes(100)
        db.upsert_nodes_bulk(nodes, batch_size=100)

        page = db.get_nodes_page(offset=0, limit=200, protocol="vmess")
        assert len(page) == 100
        for n in page:
            assert n.protocol.value == "vmess"

    def test_filter_alive_only(self, tmp_path):
        db = Database(str(tmp_path / "test.db"))
        nodes = _make_nodes(100)
        db.upsert_nodes_bulk(nodes, batch_size=100)

        page = db.get_nodes_page(offset=0, limit=200, alive_only=True)
        for n in page:
            assert n.alive is True

    def test_filter_country(self, tmp_path):
        db = Database(str(tmp_path / "test.db"))
        nodes = _make_nodes(100)
        db.upsert_nodes_bulk(nodes, batch_size=100)

        page = db.get_nodes_page(offset=0, limit=200, country="US")
        for n in page:
            assert n.country == "US"

    def test_filter_min_score(self, tmp_path):
        db = Database(str(tmp_path / "test.db"))
        nodes = _make_nodes(100)
        db.upsert_nodes_bulk(nodes, batch_size=100)

        page = db.get_nodes_page(offset=0, limit=200, min_score=90)
        for n in page:
            assert n.score >= 90

    def test_combined_filters(self, tmp_path):
        db = Database(str(tmp_path / "test.db"))
        nodes = _make_nodes(100)
        db.upsert_nodes_bulk(nodes, batch_size=100)

        page = db.get_nodes_page(
            offset=0, limit=200,
            protocol="vmess", country="US", alive_only=True, min_score=50,
        )
        for n in page:
            assert n.protocol.value == "vmess"
            assert n.country == "US"
            assert n.alive is True
            assert n.score >= 50


class TestGetNodeCount:
    def test_count_empty(self, tmp_path):
        db = Database(str(tmp_path / "test.db"))
        assert db.get_node_count() == 0

    def test_count_total(self, tmp_path):
        db = Database(str(tmp_path / "test.db"))
        nodes = _make_nodes(50)
        db.upsert_nodes_bulk(nodes, batch_size=50)
        assert db.get_node_count() == 50

    def test_count_with_filter(self, tmp_path):
        db = Database(str(tmp_path / "test.db"))
        nodes = _make_nodes(100)
        db.upsert_nodes_bulk(nodes, batch_size=100)
        assert db.get_node_count(protocol="vmess") == 100
        assert db.get_node_count(alive_only=True) > 0
        assert db.get_node_count(country="US") > 0
