# path: tests/test_github_watcher_branch.py
"""测试 GitHubWatcher 默认分支检测

验证:
- GitHubWatcher 使用 default_branch，不写死 master
- default_branch 失败时 fallback main → master
- fetch_readme / fetch_candidate_files 使用动态分支
- branch 缓存正常工作
"""

import pytest
from unittest.mock import patch, MagicMock, PropertyMock

from freeladder.source_intel.github_watcher import GitHubWatcher
from freeladder.source_intel.source_store import SourceStore
from freeladder.source_intel.link_extractor import LinkExtractor
from freeladder.source_intel.models import SourceKind


class TestGitHubWatcherBranch:
    def test_get_default_branch_from_api(self, tmp_path):
        """正常情况：从 API 获取 default_branch"""
        store = SourceStore(data_dir=tmp_path)
        watcher = GitHubWatcher(store, extractor=LinkExtractor())

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"default_branch": "main"}
        mock_response.headers = {}

        with patch("httpx.Client") as mock_client:
            mock_client.return_value.__enter__ = MagicMock(return_value=mock_client.return_value)
            mock_client.return_value.__exit__ = MagicMock(return_value=False)
            mock_client.return_value.get.return_value = mock_response

            branch = watcher.get_default_branch("test/repo")
            assert branch == "main"

    def test_get_default_branch_cache(self, tmp_path):
        """缓存命中时不重复请求 API"""
        store = SourceStore(data_dir=tmp_path)
        watcher = GitHubWatcher(store, extractor=LinkExtractor())
        watcher._branch_cache["test/repo"] = "develop"

        branch = watcher.get_default_branch("test/repo")
        assert branch == "develop"

    def test_get_default_branch_fallback_main(self, tmp_path):
        """API 失败时 fallback 到 main"""
        store = SourceStore(data_dir=tmp_path)
        watcher = GitHubWatcher(store, extractor=LinkExtractor())

        with patch("httpx.Client") as mock_client:
            mock_client.return_value.__enter__ = MagicMock(return_value=mock_client.return_value)
            mock_client.return_value.__exit__ = MagicMock(return_value=False)
            mock_client.return_value.get.side_effect = Exception("API error")

            branch = watcher.get_default_branch("test/repo")
            assert branch == "main"

    def test_get_default_branch_not_hardcoded_master(self, tmp_path):
        """确保不写死 master — API 返回什么就用什么"""
        store = SourceStore(data_dir=tmp_path)
        watcher = GitHubWatcher(store, extractor=LinkExtractor())

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"default_branch": "trunk"}
        mock_response.headers = {}

        with patch("httpx.Client") as mock_client:
            mock_client.return_value.__enter__ = MagicMock(return_value=mock_client.return_value)
            mock_client.return_value.__exit__ = MagicMock(return_value=False)
            mock_client.return_value.get.return_value = mock_response

            branch = watcher.get_default_branch("test/repo")
            assert branch == "trunk"

    def test_fetch_readme_uses_dynamic_branch(self, tmp_path):
        """fetch_readme 使用动态分支而非 master"""
        store = SourceStore(data_dir=tmp_path)
        watcher = GitHubWatcher(store, extractor=LinkExtractor())

        with patch.object(watcher, 'get_default_branch', return_value="main") as mock_branch:
            with patch.object(watcher, '_fetch_raw', return_value="# README") as mock_fetch:
                content = watcher.fetch_readme("test/repo")
                mock_branch.assert_called_once_with("test/repo")
                # URL should contain 'main', not 'master'
                call_url = mock_fetch.call_args[0][0]
                assert "/main/" in call_url
                assert "/master/" not in call_url
                assert content == "# README"

    def test_fetch_readme_fallback_main_master(self, tmp_path):
        """fetch_readme 在 default_branch 失败时 fallback main → master"""
        store = SourceStore(data_dir=tmp_path)
        watcher = GitHubWatcher(store, extractor=LinkExtractor())

        with patch.object(watcher, 'get_default_branch', return_value="develop"):
            call_count = [0]
            def mock_fetch(url):
                call_count[0] += 1
                if "develop" in url:
                    return None  # default branch fails
                if "main" in url:
                    return None  # main fails too
                if "master" in url:
                    return "# README from master"
                return None

            with patch.object(watcher, '_fetch_raw', side_effect=mock_fetch):
                content = watcher.fetch_readme("test/repo")
                assert content == "# README from master"

    def test_fetch_candidate_files_uses_dynamic_branch(self, tmp_path):
        """fetch_candidate_files 使用动态分支"""
        store = SourceStore(data_dir=tmp_path)
        watcher = GitHubWatcher(store, extractor=LinkExtractor())

        with patch.object(watcher, 'get_default_branch', return_value="main"):
            with patch.object(watcher, '_fetch_raw', return_value="proxies: []"):
                files = watcher.fetch_candidate_files("test/repo")
                # Should have made at least one call with 'main' in URL
                for call in watcher._fetch_raw.call_args_list:
                    url = call[0][0]
                    # None of the URLs should contain /master/
                    assert "/master/" not in url

    def test_branch_caching_across_calls(self, tmp_path):
        """多次调用使用缓存的分支"""
        store = SourceStore(data_dir=tmp_path)
        watcher = GitHubWatcher(store, extractor=LinkExtractor())

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"default_branch": "release"}
        mock_response.headers = {}

        with patch("httpx.Client") as mock_client:
            mock_client.return_value.__enter__ = MagicMock(return_value=mock_client.return_value)
            mock_client.return_value.__exit__ = MagicMock(return_value=False)
            mock_client.return_value.get.return_value = mock_response

            b1 = watcher.get_default_branch("test/repo")
            b2 = watcher.get_default_branch("test/repo")
            assert b1 == "release"
            assert b2 == "release"
            # Should only call API once due to caching
            assert mock_client.return_value.get.call_count == 1
