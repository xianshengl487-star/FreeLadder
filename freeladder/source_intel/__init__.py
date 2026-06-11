# path: freeladder/source_intel/__init__.py
"""Source Intelligence Engine - 源情报引擎

可发现 → 可验证 → 可评分 → 可候选 → 用户确认 → 可启用 → 可禁用 → 可持续维护
"""

from .models import SourceRecord, SourceKind, SourceFormat, SourceStatus, RepoWatchRecord, DiscoveryResult
from .source_store import SourceStore
from .link_extractor import LinkExtractor
from .source_health import SourceHealth
from .source_validator import SourceValidator
from .github_watcher import GitHubWatcher
from .repo_scanner import RepoScanner
from .non_github_discovery import NonGitHubDiscovery
from .rss_watcher import RSSWatcher
from .engine import SourceIntelEngine
from .scheduler import SourceIntelScheduler

__all__ = [
    "SourceRecord", "SourceKind", "SourceFormat", "SourceStatus",
    "RepoWatchRecord", "DiscoveryResult",
    "SourceStore", "LinkExtractor", "SourceHealth", "SourceValidator",
    "GitHubWatcher", "RepoScanner", "NonGitHubDiscovery", "RSSWatcher",
    "SourceIntelEngine", "SourceIntelScheduler",
]
