# path: freeladder/source_intel/source_store.py
"""本地 JSON 存储管理

存储文件:
- data/source_intel.json    源记录
- data/source_health.json   健康数据
- data/repo_watch.json      GitHub 仓库监控
- data/non_github_sources.json  非 GitHub 源

安全要求:
- JSON 损坏自动备份为 .bak
- 保存使用临时文件原子替换
- 写入前创建 data/ 目录
- 空文件返回空列表
- 旧字段缺失自动补默认值
"""

import json
import os
import shutil
import tempfile
import time
from pathlib import Path
from typing import Optional

from loguru import logger

from .models import SourceRecord, RepoWatchRecord, SourceStatus


class SourceStore:
    """本地 JSON 存储管理"""

    def __init__(self, data_dir: Optional[Path] = None):
        if data_dir is None:
            from freeladder.core.paths import get_data_dir
            data_dir = get_data_dir()
        self._data_dir = Path(data_dir)
        self._data_dir.mkdir(parents=True, exist_ok=True)

        self._sources_file = self._data_dir / "source_intel.json"
        self._health_file = self._data_dir / "source_health.json"
        self._repo_watch_file = self._data_dir / "repo_watch.json"
        self._non_github_file = self._data_dir / "non_github_sources.json"

    def _atomic_save(self, filepath: Path, data: list[dict]) -> None:
        """原子保存: 先写临时文件，再替换"""
        tmp_fd, tmp_path = tempfile.mkstemp(
            dir=str(self._data_dir), suffix=".tmp"
        )
        try:
            with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            # 原子替换
            shutil.move(tmp_path, str(filepath))
        except Exception:
            # 清理临时文件
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise

    def _load_json(self, filepath: Path) -> list[dict]:
        """加载 JSON，损坏时自动备份"""
        if not filepath.exists():
            return []

        try:
            content = filepath.read_text(encoding="utf-8")
            if not content.strip():
                return []
            data = json.loads(content)
            if not isinstance(data, list):
                logger.warning(f"JSON 格式异常（非列表）: {filepath}")
                return []
            return data
        except (json.JSONDecodeError, ValueError) as e:
            logger.error(f"JSON 解析失败: {filepath}, 错误: {e}")
            # 备份损坏文件
            backup_path = filepath.with_suffix(".json.bak")
            try:
                shutil.copy2(str(filepath), str(backup_path))
                logger.info(f"已备份损坏文件: {backup_path}")
            except Exception:
                pass
            return []

    def _save_json(self, filepath: Path, data: list[dict]) -> None:
        """保存 JSON"""
        self._atomic_save(filepath, data)

    # ── 源记录操作 ──

    def load_sources(self) -> list[SourceRecord]:
        """加载所有源记录"""
        raw = self._load_json(self._sources_file)
        sources = []
        for item in raw:
            try:
                sources.append(SourceRecord(**item))
            except Exception as e:
                logger.debug(f"跳过无效源记录: {e}")
        return sources

    def save_sources(self, sources: list[SourceRecord]) -> None:
        """保存所有源记录"""
        data = [s.model_dump() for s in sources]
        self._save_json(self._sources_file, data)

    def upsert_source(self, source: SourceRecord) -> None:
        """插入或更新单个源"""
        sources = self.load_sources()
        existing_idx = None
        for i, s in enumerate(sources):
            if s.id == source.id:
                existing_idx = i
                break

        if existing_idx is not None:
            sources[existing_idx] = source
        else:
            sources.append(source)

        self.save_sources(sources)

    def list_enabled(self) -> list[SourceRecord]:
        """列出所有已启用源"""
        return [s for s in self.load_sources() if s.status == SourceStatus.ENABLED]

    def list_candidates(self) -> list[SourceRecord]:
        """列出所有候选源"""
        return [s for s in self.load_sources() if s.status == SourceStatus.CANDIDATE]

    def list_failed(self) -> list[SourceRecord]:
        """列出所有失败源"""
        return [s for s in self.load_sources()
                if s.status in (SourceStatus.FAILED, SourceStatus.DEAD)]

    def get(self, source_id: str) -> Optional[SourceRecord]:
        """按 ID 获取源"""
        for s in self.load_sources():
            if s.id == source_id:
                return s
        return None

    def enable(self, source_id: str, user_confirmed: bool = True) -> bool:
        """启用源（需用户确认）"""
        sources = self.load_sources()
        for s in sources:
            if s.id == source_id:
                s.enabled = True
                s.user_confirmed = user_confirmed
                s.status = SourceStatus.ENABLED
                self.save_sources(sources)
                logger.info(f"已启用源: {s.name} ({s.id})")
                return True
        return False

    def disable(self, source_id: str) -> bool:
        """禁用源"""
        sources = self.load_sources()
        for s in sources:
            if s.id == source_id:
                s.enabled = False
                s.status = SourceStatus.DISABLED
                self.save_sources(sources)
                logger.info(f"已禁用源: {s.name} ({s.id})")
                return True
        return False

    def mark_success(
        self, source_id: str, node_count: int, protocol_stats: dict
    ) -> None:
        """标记源成功"""
        now = time.strftime("%Y-%m-%d %H:%M:%S")
        sources = self.load_sources()
        for s in sources:
            if s.id == source_id:
                s.success_count += 1
                s.fail_count = 0
                s.last_success = now
                s.last_checked = now
                s.last_node_count = node_count
                s.protocol_stats = protocol_stats
                s.last_error = ""
                # 更新平均节点数（指数移动平均）
                if s.avg_node_count == 0:
                    s.avg_node_count = float(node_count)
                else:
                    s.avg_node_count = s.avg_node_count * 0.7 + node_count * 0.3
                if s.status not in (SourceStatus.ENABLED,):
                    s.status = SourceStatus.CANDIDATE
                self.save_sources(sources)
                return

    def mark_failed(self, source_id: str, error: str) -> None:
        """标记源失败"""
        now = time.strftime("%Y-%m-%d %H:%M:%S")
        sources = self.load_sources()
        for s in sources:
            if s.id == source_id:
                s.fail_count += 1
                s.last_failed = now
                s.last_checked = now
                s.last_error = error[:200]
                s.status = SourceStatus.FAILED
                self.save_sources(sources)
                return

    def mark_stale(self, source_id: str) -> None:
        """标记源过期"""
        sources = self.load_sources()
        for s in sources:
            if s.id == source_id:
                s.status = SourceStatus.STALE
                self.save_sources(sources)
                return

    def mark_dead_if_needed(self, source_id: str, max_failures: int = 5) -> None:
        """连续失败超阈值时标记 DEAD"""
        sources = self.load_sources()
        for s in sources:
            if s.id == source_id:
                if s.fail_count >= max_failures:
                    s.status = SourceStatus.DEAD
                    s.enabled = False
                    logger.warning(f"源已标记 DEAD: {s.name} (连续失败 {s.fail_count} 次)")
                self.save_sources(sources)
                return

    def remove_source(self, source_id: str) -> bool:
        """删除源"""
        sources = self.load_sources()
        before = len(sources)
        sources = [s for s in sources if s.id != source_id]
        if len(sources) < before:
            self.save_sources(sources)
            return True
        return False

    # ── 仓库监控记录 ──

    def load_repo_watch(self) -> list[RepoWatchRecord]:
        """加载仓库监控记录"""
        raw = self._load_json(self._repo_watch_file)
        records = []
        for item in raw:
            try:
                records.append(RepoWatchRecord(**item))
            except Exception:
                pass
        return records

    def save_repo_watch(self, records: list[RepoWatchRecord]) -> None:
        """保存仓库监控记录"""
        data = [r.model_dump() for r in records]
        self._save_json(self._repo_watch_file, data)

    def upsert_repo_watch(self, record: RepoWatchRecord) -> None:
        """插入或更新仓库监控记录"""
        records = self.load_repo_watch()
        existing_idx = None
        for i, r in enumerate(records):
            if r.repo == record.repo:
                existing_idx = i
                break

        if existing_idx is not None:
            records[existing_idx] = record
        else:
            records.append(record)

        self.save_repo_watch(records)
