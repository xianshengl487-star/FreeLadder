# path: freeladder/source_intel/engine.py
"""源情报引擎总控

所有入口统一走 Engine。GUI / CLI / scraper 都通过 Engine 调用。
"""

from typing import Optional

from loguru import logger

from .models import SourceRecord, SourceStatus
from .source_store import SourceStore
from .source_health import SourceHealth
from .source_validator import SourceValidator
from .github_watcher import GitHubWatcher
from .non_github_discovery import NonGitHubDiscovery
from .rss_watcher import RSSWatcher
from .link_extractor import LinkExtractor


class SourceIntelEngine:
    """源情报引擎总控"""

    def __init__(self, config=None):
        if config is None:
            from freeladder.core.config import get_config
            config = get_config().source_intel
        self._config = config
        self._store = SourceStore()
        self._health = SourceHealth(
            stale_days=config.stale_source_days,
            remove_dead_after=config.remove_dead_after_failures,
        )
        self._validator = SourceValidator(config)
        self._extractor = LinkExtractor()
        self._github_watcher = GitHubWatcher(self._store, config, self._extractor)
        self._non_github = NonGitHubDiscovery(self._store, config, self._extractor)
        self._rss_watcher = RSSWatcher(self._store, config, self._extractor)

    @property
    def store(self) -> SourceStore:
        return self._store

    def refresh_sources(self, on_progress=None, cancel_token=None) -> dict:
        """刷新所有源候选状态"""
        results = {"github": 0, "non_github": 0, "rss": 0, "validated": 0}

        # GitHub 源监控
        if self._config.github_watch_enabled:
            github_sources = self.discover_github_sources(on_progress, cancel_token)
            results["github"] = len(github_sources)

        # 非 GitHub 源发现
        if self._config.non_github_discovery_enabled:
            non_github = self.discover_non_github_sources(on_progress, cancel_token)
            results["non_github"] = len(non_github)

        # RSS 监控
        if self._config.rss_watch_enabled:
            rss = self._discover_rss_sources(on_progress, cancel_token)
            results["rss"] = len(rss)

        # 验证候选源
        if self._config.validate_before_enable:
            validated = self.validate_candidates(on_progress, cancel_token)
            results["validated"] = validated

        return results

    def discover_github_sources(self, on_progress=None, cancel_token=None) -> list[SourceRecord]:
        """发现 GitHub 源"""
        if not self._config.github_watch_enabled:
            return []

        sources = self._github_watcher.check_all(on_progress, cancel_token)
        # 去重并存入 store
        for s in sources:
            existing = self._store.get(s.id)
            if not existing:
                s.status = SourceStatus.CANDIDATE
                self._store.upsert_source(s)

        return sources

    def discover_non_github_sources(self, on_progress=None, cancel_token=None) -> list[SourceRecord]:
        """发现非 GitHub 源"""
        if not self._config.non_github_discovery_enabled:
            return []

        # 优先使用用户配置的 non_github_sites，否则使用预置种子页面
        sites = getattr(self._config, "non_github_sites", None)
        if not sites:
            sites = self._non_github.get_seed_public_pages()

        sources = self._non_github.discover_from_sites(sites, on_progress, cancel_token)

        for s in sources:
            existing = self._store.get(s.id)
            if not existing:
                s.status = SourceStatus.CANDIDATE
                self._store.upsert_source(s)

        return sources

    def _discover_rss_sources(self, on_progress=None, cancel_token=None) -> list[SourceRecord]:
        """发现 RSS 源"""
        if not self._config.rss_watch_enabled:
            return []

        # 获取用户配置的 RSS feeds
        sources = self._rss_watcher.check_all([], on_progress, cancel_token)

        for s in sources:
            existing = self._store.get(s.id)
            if not existing:
                s.status = SourceStatus.CANDIDATE
                self._store.upsert_source(s)

        return sources

    def validate_candidates(self, on_progress=None, cancel_token=None) -> int:
        """验证所有候选源"""
        candidates = self._store.list_candidates()
        if not candidates:
            return 0

        total = len(candidates)
        validated = 0

        for i, source in enumerate(candidates, 1):
            if cancel_token and cancel_token.cancelled:
                break

            result = self._validator.validate(source)
            if result["valid"]:
                source = self._health.update_after_success(
                    source, result["node_count"], result["protocol_stats"]
                )
                validated += 1
            else:
                source = self._health.update_after_failure(source, result["error"])

            self._store.upsert_source(source)

            if on_progress:
                on_progress(i, total, f"验证 {source.name}")

        return validated

    def get_enabled_source_urls(self) -> list[str]:
        """获取所有已启用源的 URL"""
        enabled = self._store.list_enabled()
        return [s.url for s in enabled]

    def get_candidate_sources(self) -> list[SourceRecord]:
        """获取所有候选源"""
        return self._store.list_candidates()

    def enable_source(self, source_id: str, user_confirmed: bool = True) -> bool:
        """启用源（需用户确认）"""
        source = self._store.get(source_id)
        if not source:
            return False

        if self._config.require_user_confirm_for_new_sources and not user_confirmed:
            logger.warning(f"源未确认: {source.name}")
            return False

        return self._store.enable(source_id, user_confirmed)

    def disable_source(self, source_id: str) -> bool:
        """禁用源"""
        return self._store.disable(source_id)

    def remove_dead_sources(self) -> int:
        """清理 DEAD 源"""
        dead = [s for s in self._store.load_sources() if s.status == SourceStatus.DEAD]
        for s in dead:
            self._store.remove_source(s.id)
        return len(dead)
