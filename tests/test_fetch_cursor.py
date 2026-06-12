# path: tests/test_fetch_cursor.py
"""分批获取游标测试"""

from freeladder.core.fetch_cursor import FetchCursor


class TestFetchCursor:
    def test_batch_rotation(self, tmp_path):
        cursor = FetchCursor(tmp_path)
        sources = [f"https://example.com/{i}" for i in range(5)]

        batch1, info1 = cursor.select_batch(sources, 2)
        assert len(batch1) == 2
        assert info1["batch_no"] == 1

        batch2, info2 = cursor.select_batch(sources, 2)
        assert len(batch2) == 2
        assert batch1 != batch2

        batch3, _ = cursor.select_batch(sources, 2)
        batch4, _ = cursor.select_batch(sources, 2)
        batch5, _ = cursor.select_batch(sources, 2)
        # 5 个源每批 2 个，第 6 批应回到开头
        batch6, info6 = cursor.select_batch(sources, 2)
        assert batch6 == batch1
        assert info6["batch_no"] == 1

    def test_batch_smaller_than_total(self, tmp_path):
        cursor = FetchCursor(tmp_path)
        sources = ["a", "b", "c"]
        batch, info = cursor.select_batch(sources, 10)
        assert len(batch) == 3
        assert info["batch_size"] == 3