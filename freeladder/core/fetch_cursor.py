# path: freeladder/core/fetch_cursor.py
"""分批获取游标：每次点击只抓取一部分订阅源"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional


class FetchCursor:
    """记录下次应从哪个源索引开始分批抓取"""

    def __init__(self, data_dir: Path):
        self._file = Path(data_dir) / "fetch_cursor.json"

    def _load(self) -> dict:
        if not self._file.exists():
            return {"next_index": 0}
        try:
            data = json.loads(self._file.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
        except (json.JSONDecodeError, OSError):
            pass
        return {"next_index": 0}

    def _save(self, data: dict) -> None:
        self._file.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._file.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(self._file)

    def select_batch(
        self,
        sources: list[str],
        batch_size: int,
    ) -> tuple[list[str], dict]:
        """从源列表中选取下一批 URL（循环）"""
        unique_sources = list(dict.fromkeys(sources))
        total = len(unique_sources)
        if total == 0 or batch_size <= 0:
            return [], {"total_sources": 0, "batch_size": 0, "batch_no": 0, "total_batches": 0}

        state = self._load()
        start = int(state.get("next_index", 0)) % total
        size = min(batch_size, total)

        batch: list[str] = []
        for i in range(size):
            batch.append(unique_sources[(start + i) % total])

        next_index = (start + size) % total
        total_batches = (total + batch_size - 1) // batch_size
        batch_no = start // batch_size + 1

        self._save({
            "next_index": next_index,
            "total_sources": total,
            "last_batch_size": size,
            "last_batch_start": start,
        })

        return batch, {
            "total_sources": total,
            "batch_size": size,
            "batch_no": batch_no,
            "total_batches": total_batches,
            "start_index": start,
            "next_index": next_index,
        }

    def reset(self) -> None:
        """重置游标"""
        if self._file.exists():
            self._file.unlink()