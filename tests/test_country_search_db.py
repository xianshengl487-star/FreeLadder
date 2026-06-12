# path: tests/test_country_search_db.py
"""数据库国家搜索测试"""

from freeladder.core.database import Database
from freeladder.core.models import Node, Protocol


class TestCountrySearchDb:
    def test_search_by_country_name_and_alias(self, tmp_path):
        db = Database(str(tmp_path / "test.db"))
        nodes = [
            Node(
                node_key="vmess:jp1:443",
                raw_hash="h1",
                protocol=Protocol.VMESS,
                server="1.2.3.4",
                port=443,
                name="🇯🇵 VMESS-日本-测试",
                raw_uri="vmess://test1",
                country="日本",
            ),
            Node(
                node_key="vmess:us1:443",
                raw_hash="h2",
                protocol=Protocol.VMESS,
                server="5.6.7.8",
                port=443,
                name="🇺🇸 VMESS-美国-测试",
                raw_uri="vmess://test2",
                country="美国",
            ),
        ]
        db.upsert_nodes_bulk(nodes, batch_size=10)

        jp = db.get_nodes_page(country="JP")
        us = db.get_nodes_page(country="美国")
        assert len(jp) == 1
        assert len(us) == 1
        assert jp[0].country == "日本"