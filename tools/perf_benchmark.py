# path: tools/perf_benchmark.py
"""FreeLadder 性能基准测试

测试:
1. 1k/5k/10k 节点 bulk upsert
2. get_nodes_page 加载速度
3. GUI 渲染最大行数检查
4. FetchPipeline mock 100 个源
5. DBWriter queue 压力
"""

import sys
import time
import tempfile
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))


def bench_bulk_upsert():
    """批量入库性能测试"""
    from freeladder.core.database import Database
    from freeladder.core.models import Node, Protocol

    results = {}
    for count in [1000, 5000, 10000]:
        nodes = []
        for i in range(count):
            nodes.append(Node(
                node_key=f"vmess:bench{i}:443",
                raw_hash=f"bench{i:06d}",
                protocol=Protocol.VMESS,
                server=f"10.{(i // 256) % 256}.{i % 256}.1",
                port=443,
                name=f"Bench Node {i}",
                raw_uri=f"vmess://bench{i}",
            ))

        with tempfile.TemporaryDirectory() as tmpdir:
            db = Database(str(Path(tmpdir) / "bench.db"))
            t0 = time.time()
            db.upsert_nodes_bulk(nodes, batch_size=500)
            elapsed = time.time() - t0
            results[f"upsert_{count}"] = elapsed
            print(f"  Bulk upsert {count} nodes: {elapsed:.3f}s")
            db.close()

    return results


def bench_page_load():
    """分页加载性能测试"""
    from freeladder.core.database import Database
    from freeladder.core.models import Node, Protocol

    with tempfile.TemporaryDirectory() as tmpdir:
        db = Database(str(Path(tmpdir) / "bench.db"))
        nodes = []
        for i in range(5000):
            nodes.append(Node(
                node_key=f"vmess:page{i}:443",
                raw_hash=f"page{i:06d}",
                protocol=Protocol.VMESS,
                server=f"10.{(i // 256) % 256}.{i % 256}.1",
                port=443,
                name=f"Page Node {i}",
                raw_uri=f"vmess://page{i}",
            ))
        db.upsert_nodes_bulk(nodes, batch_size=500)

        # Load 200 nodes, 25 times
        t0 = time.time()
        for offset in range(0, 5000, 200):
            page = db.get_nodes_page(offset=offset, limit=200)
            assert len(page) <= 200
        elapsed = time.time() - t0
        print(f"  Page load 200 nodes x25 pages: {elapsed:.3f}s")
        db.close()

    return {"page_load": elapsed}


def bench_db_writer():
    """DBWriter 队列压力测试"""
    from freeladder.core.database import Database
    from freeladder.core.models import Node, Protocol
    from freeladder.tasks.db_writer import DBWriter

    with tempfile.TemporaryDirectory() as tmpdir:
        db = Database(str(Path(tmpdir) / "bench.db"))
        writer = DBWriter(db, batch_size=500, queue_max_size=3000)

        nodes = []
        for i in range(2000):
            nodes.append(Node(
                node_key=f"vmess:dbw{i}:443",
                raw_hash=f"dbw{i:06d}",
                protocol=Protocol.VMESS,
                server=f"10.{(i // 256) % 256}.{i % 256}.1",
                port=443,
                name=f"DBW Node {i}",
                raw_uri=f"vmess://dbw{i}",
            ))

        t0 = time.time()
        writer.start()
        # Submit in batches to simulate real pipeline
        batch_size = 200
        for start in range(0, len(nodes), batch_size):
            writer.submit_nodes(nodes[start:start + batch_size])
        writer.close()
        elapsed = time.time() - t0

        print(f"  DBWriter 2000 nodes: {elapsed:.3f}s")
        print(f"  Stats: received={writer.stats.received}, batches={writer.stats.batches}")
        db.close()

    return {"db_writer": elapsed}


def bench_gui_render():
    """GUI 渲染行数检查"""
    from freeladder.core.database import Database
    from freeladder.core.models import Node, Protocol

    with tempfile.TemporaryDirectory() as tmpdir:
        db = Database(str(Path(tmpdir) / "bench.db"))
        nodes = []
        for i in range(1000):
            nodes.append(Node(
                node_key=f"vmess:gui{i}:443",
                raw_hash=f"gui{i:06d}",
                protocol=Protocol.VMESS,
                server=f"10.{(i // 256) % 256}.{i % 256}.1",
                port=443,
                name=f"GUI Node {i}",
                raw_uri=f"vmess://gui{i}",
            ))
        db.upsert_nodes_bulk(nodes, batch_size=500)

        # Simulate GUI pagination
        page_size = 200
        max_render = 300
        t0 = time.time()
        page = db.get_nodes_page(offset=0, limit=page_size)
        render_nodes = page[:max_render]
        elapsed = time.time() - t0
        print(f"  GUI render check: {len(render_nodes)} nodes, {elapsed:.3f}s")
        assert len(render_nodes) <= max_render
        db.close()

    return {"gui_render": elapsed}


def bench_fetch_pipeline_mock():
    """FetchPipeline mock 100 个源"""
    from unittest.mock import patch, MagicMock

    mock_nodes = []
    from freeladder.core.models import Node, Protocol
    for i in range(50):
        mock_nodes.append(Node(
            node_key=f"vmess:fetch{i}:443",
            raw_hash=f"fetch{i:06d}",
            protocol=Protocol.VMESS,
            server=f"10.{(i // 256) % 256}.{i % 256}.1",
            port=443,
            name=f"Fetch Node {i}",
            raw_uri=f"vmess://fetch{i}",
        ))

    def mock_scrape_source(url, timeout=15):
        import hashlib
        import random
        random.seed(hash(url))
        return random.sample(mock_nodes, min(20, len(mock_nodes)))

    from freeladder.core.database import Database
    from freeladder.core.config import Config, ScraperConfig, SourceIntelConfig, PerformanceConfig
    from freeladder.tasks.fetch_pipeline import run_fetch_pipeline
    from freeladder.source_intel.engine import SourceIntelEngine

    tmpdir = tempfile.mkdtemp()
    try:
        db = Database(str(Path(tmpdir) / "bench.db"))
        cfg = Config(
            scraper=ScraperConfig(builtin_enabled=False),
            source_intel=SourceIntelConfig(enabled=False),
            performance=PerformanceConfig(
                fetch_workers=8,
                db_batch_size=500,
                db_queue_max_size=3000,
                max_pending_futures=200,
                max_total_nodes_per_task=10000,
                max_nodes_per_source=1000,
                progress_update_interval_ms=500,
                source_timeout_seconds=5,
            ),
        )

        urls = [f"https://example.com/sub{i}" for i in range(100)]

        with patch("freeladder.tasks.fetch_pipeline.scrape_source", side_effect=mock_scrape_source):
            with patch.object(SourceIntelEngine, "get_enabled_source_urls", return_value=urls):
                t0 = time.time()
                stats = run_fetch_pipeline(db, config=cfg)
                elapsed = time.time() - t0

                print(f"  FetchPipeline mock 100 sources: {elapsed:.3f}s")
                print(f"  Stats: {stats}")

        db.close()
        return {"fetch_pipeline_mock": elapsed}
    finally:
        import shutil
        shutil.rmtree(tmpdir, ignore_errors=True)


def main():
    """运行所有性能测试"""
    print("=" * 60)
    print("FreeLadder 性能基准测试")
    print("=" * 60)

    print("\n[1] Bulk Upsert (1k/5k/10k)")
    r1 = bench_bulk_upsert()

    print("\n[2] Page Load (200 nodes x25)")
    r2 = bench_page_load()

    print("\n[3] DBWriter (2000 nodes)")
    r3 = bench_db_writer()

    print("\n[4] GUI Render Check")
    r4 = bench_gui_render()

    print("\n[5] FetchPipeline Mock (100 sources)")
    r5 = bench_fetch_pipeline_mock()

    print("\n" + "=" * 60)
    print("Summary:")
    all_results = {**r1, **r2, **r3, **r4, **r5}
    for k, v in all_results.items():
        print(f"  {k}: {v:.3f}s" if isinstance(v, float) else f"  {k}: {v}")
    print("=" * 60)

    return 0


if __name__ == "__main__":
    sys.exit(main())
