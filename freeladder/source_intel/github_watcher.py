# path: freeladder/source_intel/github_watcher.py
"""GitHub 仓库监控器

监控指定 GitHub 仓库，检查 README、候选文件、releases、commits。
使用 ETag / Last-Modified 做条件请求。
"""

import time
from typing import Optional

import httpx
from loguru import logger

from .models import SourceRecord, RepoWatchRecord, SourceKind, SourceFormat
from .source_store import SourceStore
from .repo_scanner import RepoScanner
from .link_extractor import LinkExtractor

# 默认 seed repos（覆盖多个地区/语言的开源社区）
SEED_GITHUB_REPOS = [
    # ── 综合聚合 ──
    "mfuu/v2ray",
    "anaer/Sub",
    "ermaozi/get_subscribe",
    "Pawdroid/Free-servers",
    "vxiaov/free_proxies",
    "xiaoji235/airport-free",
    "mermeroo/V2RAY-CLASH-BASE64-Subscription.Links",
    "coldwater-10/V2RAY-and-CLASH-Subscription-Links",
    "peasoft/NoMoreWalls",
    "mahdibland/V2RayAggregator",
    "aiboboxx/v2rayfree",
    "OPEN-VPN/0",
    "ripaojiedian/freenode",
    "ts-sf/flying",
    "xrayfree/v2rayfree",
    # ── 中东/土耳其/波斯语 ──
    "MrMohewa/Nodes",
    "HosseinKarami27/Bestfree",
    "sadevans/SUB",
    "AliMohaMadi/Naproxy",
    "Epodonios/v2ray-configs",
    "yebekhe/TelegramV2rayCollector",
    # ── 拉丁美洲/西班牙语 ──
    "AresS31/v2ray-free",
    "RiriIsmail/sub",
    # ── 欧洲/多语言 ──
    "LalatinaHub/Inventory",
    "barry-far/V2ray-Configs",
    "MrMohebi/xray-proxy-grabber-telegram",
    "Leon406/SubCrawler",
    # ── 多协议聚合 ──
    "freefq/free",
    "tbbatbb/Proxy",
    "soroushmirzaei/telegram-configs-collector",
]

# 候选文件名
CANDIDATE_FILES = [
    "README.md", "readme.md",
    "sub", "sub.txt", "subs.txt", "subscribe",
    "clash.yaml", "clash.yml", "config.yaml", "proxy.yaml",
    "nodes.txt", "v2ray", "v2ray.txt", "base64",
]


class GitHubWatcher:
    """GitHub 仓库监控器"""

    def __init__(self, store: SourceStore, config=None, extractor: Optional[LinkExtractor] = None):
        if config is None:
            from freeladder.core.config import get_config
            config = get_config().source_intel
        self._config = config
        self._store = store
        self._extractor = extractor or LinkExtractor()
        self._scanner = RepoScanner(self._extractor)
        self._api_base = "https://api.github.com"
        self._raw_base = "https://raw.githubusercontent.com"
        self._branch_cache: dict[str, str] = {}  # repo -> branch

    def _get_headers(self, etag: str = "", last_modified: str = "") -> dict:
        """构建请求头"""
        headers = {"User-Agent": self._config.user_agent}
        if self._config.github_token:
            headers["Authorization"] = f"token {self._config.github_token}"
        if etag:
            headers["If-None-Match"] = etag
        if last_modified:
            headers["If-Modified-Since"] = last_modified
        return headers

    def check_repo(self, repo: str) -> list[SourceRecord]:
        """检查单个仓库"""
        logger.info(f"检查仓库: {repo}")
        all_sources = []

        try:
            # 获取仓库监控记录
            watch_records = self._store.load_repo_watch()
            watch_record = None
            for r in watch_records:
                if r.repo == repo:
                    watch_record = r
                    break

            if watch_record is None:
                watch_record = RepoWatchRecord(repo=repo, enabled=True)

            # 检查是否有更新
            has_update = self._check_repo_update(repo, watch_record)
            if not has_update and self._config.github_use_etag:
                logger.debug(f"仓库无更新: {repo}")
                watch_record.last_checked = time.strftime("%Y-%m-%d %H:%M:%S")
                self._store.upsert_repo_watch(watch_record)
                return []

            # 扫描 README
            readme = self.fetch_readme(repo)
            if readme:
                sources = self._scanner.scan_readme(repo, readme)
                all_sources.extend(sources)

            # 扫描候选文件
            files = self.fetch_candidate_files(repo)
            if files:
                sources = self._scanner.scan_candidate_files(repo, files)
                all_sources.extend(sources)

            # 扫描 releases
            release = self.get_releases_info(repo)
            if release:
                sources = self._scanner.scan_release_body(repo, release)
                all_sources.extend(sources)

            # 更新监控记录
            watch_record.last_checked = time.strftime("%Y-%m-%d %H:%M:%S")
            self._store.upsert_repo_watch(watch_record)

            logger.info(f"从 {repo} 发现 {len(all_sources)} 个候选源")
            return all_sources

        except Exception as e:
            logger.error(f"检查仓库失败 {repo}: {e}")
            # 记录失败
            watch_record = RepoWatchRecord(
                repo=repo, fail_count=(watch_record.fail_count if watch_record else 0) + 1,
                last_error=str(e)[:200]
            )
            self._store.upsert_repo_watch(watch_record)
            return []

    def check_all(self, on_progress=None, cancel_token=None) -> list[SourceRecord]:
        """检查所有种子仓库"""
        repos = SEED_GITHUB_REPOS[:self._config.github_max_repos_per_run]
        all_sources = []
        total = len(repos)

        for i, repo in enumerate(repos, 1):
            if cancel_token and cancel_token.cancelled:
                break

            sources = self.check_repo(repo)
            all_sources.extend(sources)

            if on_progress:
                on_progress(i, total, f"检查 {repo}")

            # 限速：每个请求间隔 1 秒
            time.sleep(1)

        return all_sources

    def _check_repo_update(self, repo: str, watch_record: RepoWatchRecord) -> bool:
        """检查仓库是否有更新（使用 ETag / Last-Modified）"""
        if not self._config.github_use_etag:
            return True

        headers = self._get_headers(watch_record.etag, watch_record.last_modified)
        url = f"{self._api_base}/repos/{repo}"

        try:
            with httpx.Client(timeout=self._config.request_timeout_seconds) as client:
                resp = client.get(url, headers=headers)

                if resp.status_code == 304:
                    return False  # 无更新

                if resp.status_code == 403:
                    logger.warning(f"GitHub API 限流: {repo}")
                    watch_record.last_error = "rate_limit"
                    return False

                resp.raise_for_status()

                # 更新 ETag / Last-Modified
                if "etag" in resp.headers:
                    watch_record.etag = resp.headers["etag"]
                if "last-modified" in resp.headers:
                    watch_record.last_modified = resp.headers["last-modified"]

                # 检查 commit sha
                data = resp.json()
                commit_sha = data.get("default_branch", "")
                if commit_sha:
                    watch_record.last_commit_sha = commit_sha

                return True

        except httpx.TimeoutException:
            logger.debug(f"检查仓库超时: {repo}")
            return True
        except Exception as e:
            logger.debug(f"检查仓库失败 {repo}: {e}")
            return True

    def fetch_readme(self, repo: str) -> str:
        """获取 README 内容（自动检测默认分支，fallback main→master）"""
        branch = self.get_default_branch(repo)
        # 尝试默认分支
        url = f"{self._raw_base}/{repo}/{branch}/README.md"
        content = self._fetch_raw(url)
        if content:
            return content
        # fallback: main → master
        for fallback in ("main", "master"):
            if fallback == branch:
                continue
            url = f"{self._raw_base}/{repo}/{fallback}/README.md"
            content = self._fetch_raw(url)
            if content:
                return content
        return ""

    def fetch_candidate_files(self, repo: str) -> dict[str, str]:
        """获取候选文件内容（自动检测默认分支）"""
        branch = self.get_default_branch(repo)
        files = {}
        for filename in CANDIDATE_FILES:
            if filename.lower() == "readme.md":
                continue  # 已单独处理
            # 尝试默认分支
            url = f"{self._raw_base}/{repo}/{branch}/{filename}"
            content = self._fetch_raw(url)
            if not content:
                # fallback: main → master
                for fallback in ("main", "master"):
                    if fallback == branch:
                        continue
                    url = f"{self._raw_base}/{repo}/{fallback}/{filename}"
                    content = self._fetch_raw(url)
                    if content:
                        break
            if content:
                files[filename] = content
        return files

    def get_default_branch(self, repo: str) -> str:
        """获取仓库默认分支（带缓存，失败返回 main）"""
        if repo in self._branch_cache:
            return self._branch_cache[repo]

        headers = self._get_headers()
        url = f"{self._api_base}/repos/{repo}"
        try:
            with httpx.Client(timeout=self._config.request_timeout_seconds) as client:
                resp = client.get(url, headers=headers)
                if resp.status_code == 200:
                    data = resp.json()
                    branch = data.get("default_branch", "main")
                    self._branch_cache[repo] = branch
                    return branch
        except Exception as e:
            logger.debug(f"获取默认分支失败 {repo}: {e}")

        # fallback
        self._branch_cache[repo] = "main"
        return "main"

    def _fetch_raw(self, url: str) -> str:
        """获取 raw 文件内容"""
        headers = self._get_headers()
        try:
            with httpx.Client(timeout=self._config.request_timeout_seconds) as client:
                resp = client.get(url, headers=headers)
                if resp.status_code == 200:
                    return resp.text
        except Exception as e:
            logger.debug(f"获取文件失败 {url}: {e}")
        return ""

    def get_latest_commit_info(self, repo: str) -> dict:
        """获取最新 commit 信息"""
        headers = self._get_headers()
        url = f"{self._api_base}/repos/{repo}/commits?per_page=1"
        try:
            with httpx.Client(timeout=self._config.request_timeout_seconds) as client:
                resp = client.get(url, headers=headers)
                if resp.status_code == 200:
                    data = resp.json()
                    if data:
                        return data[0]
        except Exception:
            pass
        return {}

    def get_releases_info(self, repo: str) -> dict:
        """获取最新 release 信息"""
        headers = self._get_headers()
        url = f"{self._api_base}/repos/{repo}/releases/latest"
        try:
            with httpx.Client(timeout=self._config.request_timeout_seconds) as client:
                resp = client.get(url, headers=headers)
                if resp.status_code == 200:
                    return resp.json()
        except Exception:
            pass
        return {}
