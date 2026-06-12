"""可用节点应排在列表最前"""

from freeladder.core.database import Database
from freeladder.core.models import Node, Protocol


def _node(server: str, port: int, alive: bool, score: float, latency=None) -> Node:
    return Node(
        protocol=Protocol.VMESS,
        server=server,
        port=port,
        alive=alive,
        score=score,
        latency=latency,
    )


def test_get_nodes_page_alive_first(tmp_path):
    db = Database(str(tmp_path / "test.db"))
    db.upsert_nodes([
        _node("10.0.0.1", 4001, False, 10.0, 100),
        _node("10.0.0.2", 4002, True, 50.0, 200),
        _node("10.0.0.3", 4003, True, 90.0, 50),
        _node("10.0.0.4", 4004, False, 80.0, 30),
    ])

    page = db.get_nodes_page(offset=0, limit=10)

    assert len(page) == 4
    assert page[0].alive is True and page[0].score == 90.0
    assert page[1].alive is True and page[1].score == 50.0
    assert page[2].alive is False and page[2].score == 80.0
    assert page[3].alive is False and page[3].score == 10.0


def test_get_all_nodes_alive_first(tmp_path):
    db = Database(str(tmp_path / "test.db"))
    db.upsert_nodes([
        _node("10.0.1.1", 5001, False, 99.0),
        _node("10.0.1.2", 5002, True, 1.0),
    ])

    nodes = db.get_all_nodes()
    assert nodes[0].alive is True
    assert nodes[1].alive is False