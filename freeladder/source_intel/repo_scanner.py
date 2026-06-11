# path: freeladder/source_intel/repo_scanner.py
"""GitHub 仓库内容扫描器

对 GitHub 仓库内容做轻量候选扫描。
只扫描 README、候选文件、release body。
不全量 clone、不递归扫所有目录、不下载大文件。
"""

from loguru import logger

from .link_extractor import LinkExtractor
from .models import SourceRecord


class RepoScanner:
    """GitHub 仓库内容扫描器"""

    def __init__(self, extractor: LinkExtractor):
        self._extractor = extractor

    def scan_readme(self, repo: str, text: str) -> list[SourceRecord]:
        """扫描 README 内容提取候选源"""
        if not text:
            return []
        sources = self._extractor.extract_from_text(
            text, discovered_from=f"github:{repo}/README"
        )
        # 标记 repo 信息
        for s in sources:
            s.repo = repo
            s.homepage = f"https://github.com/{repo}"
        logger.debug(f"从 {repo}/README 提取到 {len(sources)} 个候选源")
        return sources

    def scan_candidate_files(self, repo: str, files: dict[str, str]) -> list[SourceRecord]:
        """扫描候选文件提取源"""
        all_sources = []
        for filename, content in files.items():
            if not content:
                continue
            sources = self._extractor.extract_from_text(
                content, discovered_from=f"github:{repo}/{filename}"
            )
            for s in sources:
                s.repo = repo
                s.homepage = f"https://github.com/{repo}"
            all_sources.extend(sources)
        logger.debug(f"从 {repo} 候选文件提取到 {len(all_sources)} 个候选源")
        return all_sources

    def scan_release_body(self, repo: str, release_data: dict) -> list[SourceRecord]:
        """扫描 release body 提取源"""
        body = release_data.get("body", "")
        if not body:
            return []
        sources = self._extractor.extract_from_text(
            body, discovered_from=f"github:{repo}/release"
        )
        for s in sources:
            s.repo = repo
            s.homepage = f"https://github.com/{repo}"
        logger.debug(f"从 {repo}/release 提取到 {len(sources)} 个候选源")
        return sources
