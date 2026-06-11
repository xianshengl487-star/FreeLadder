# path: freeladder/source_intel/models.py
"""源情报引擎数据模型"""

import hashlib
import re
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class SourceKind(str, Enum):
    """源类型"""
    GITHUB_RAW = "github_raw"
    GITHUB_REPO = "github_repo"
    GITHUB_PAGES = "github_pages"
    JSDELIVR = "jsdelivr"
    RSS = "rss"
    WEBPAGE = "webpage"
    DIRECT = "direct"
    LOCAL = "local"


class SourceFormat(str, Enum):
    """源格式"""
    AUTO = "auto"
    CLASH = "clash"
    BASE64 = "base64"
    TEXT = "text"
    YAML = "yaml"


class SourceStatus(str, Enum):
    """源状态"""
    CANDIDATE = "candidate"
    ENABLED = "enabled"
    DISABLED = "disabled"
    FAILED = "failed"
    STALE = "stale"
    DEAD = "dead"


def _make_source_id(url: str) -> str:
    """基于 URL 生成稳定 ID (SHA256 前 16 位)"""
    normalized = _normalize_url(url)
    h = hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]
    return h


def _normalize_url(url: str) -> str:
    """URL 归一化: 去尾部斜杠、统一 scheme"""
    url = url.strip()
    if not url:
        return ""
    # 去尾部斜杠
    url = url.rstrip("/")
    # 统一 https
    if url.startswith("http://"):
        url = "https://" + url[7:]
    return url.lower()


class SourceRecord(BaseModel):
    """单个源的完整记录"""
    id: str = ""
    name: str = ""
    url: str = ""

    kind: SourceKind = SourceKind.DIRECT
    format: SourceFormat = SourceFormat.AUTO

    repo: str = ""
    homepage: str = ""
    discovered_from: str = ""

    enabled: bool = False
    user_confirmed: bool = False
    status: SourceStatus = SourceStatus.CANDIDATE

    etag: str = ""
    last_modified: str = ""

    last_checked: str = ""
    last_changed: str = ""
    last_success: str = ""
    last_failed: str = ""

    success_count: int = 0
    fail_count: int = 0
    last_error: str = ""

    last_node_count: int = 0
    avg_node_count: float = 0.0
    protocol_stats: dict = Field(default_factory=dict)

    quality_score: float = 0.0
    tags: list[str] = Field(default_factory=list)

    def model_post_init(self, __context) -> None:
        """初始化后自动生成 ID"""
        if not self.id and self.url:
            self.id = _make_source_id(self.url)


class RepoWatchRecord(BaseModel):
    """GitHub 仓库监控记录"""
    repo: str = ""
    enabled: bool = True
    user_confirmed: bool = False
    etag: str = ""
    last_modified: str = ""
    last_commit_sha: str = ""
    last_release_tag: str = ""
    last_checked: str = ""
    last_changed: str = ""
    fail_count: int = 0
    last_error: str = ""


class DiscoveryResult(BaseModel):
    """发现结果"""
    source: SourceRecord
    reason: str = ""
    confidence: float = 0.0
