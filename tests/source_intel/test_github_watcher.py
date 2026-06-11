# path: tests/source_intel/test_github_watcher.py
"""测试 GitHubWatcher"""

import pytest
from unittest.mock import patch, MagicMock

from freeladder.source_intel.github_watcher import GitHubWatcher, SEED_GITHUB_REPOS, CANDIDATE_FILES
from freeladder.source_intel.source_store import SourceStore
from freeladder.source_intel.link_extractor import LinkExtractor


class TestGitHubWatcher:
    def test_seed_repos_not_empty(self):
        assert len(SEED_GITHUB_REPOS) > 0

    def test_candidate_files_not_empty(self):
        assert len(CANDIDATE_FILES) > 0

    def test_check_repo_handles_error(self, source_store):
        watcher = GitHubWatcher(source_store)
        with patch.object(watcher, '_check_repo_update', return_value=True):
            with patch.object(watcher, 'fetch_readme', side_effect=Exception("network error")):
                sources = watcher.check_repo("test/repo")
                # Should not crash
                assert isinstance(sources, list)

    def test_check_repo_304_not_modified(self, source_store):
        watcher = GitHubWatcher(source_store)
        with patch.object(watcher, '_check_repo_update', return_value=False):
            sources = watcher.check_repo("test/repo")
            assert sources == []

    def test_check_all_cancellation(self, source_store):
        watcher = GitHubWatcher(source_store)
        cancel_token = MagicMock()
        cancel_token.cancelled = True
        sources = watcher.check_all(cancel_token=cancel_token)
        assert sources == []

    def test_fetch_readme_handles_timeout(self, source_store):
        watcher = GitHubWatcher(source_store)
        with patch('httpx.Client') as mock_client:
            mock_client.return_value.__enter__ = MagicMock(return_value=mock_client.return_value)
            mock_client.return_value.__exit__ = MagicMock(return_value=False)
            mock_client.return_value.get.side_effect = Exception("timeout")
            result = watcher.fetch_readme("test/repo")
            assert result == ""

    def test_rate_limit_handling(self, source_store):
        watcher = GitHubWatcher(source_store)
        with patch('httpx.Client') as mock_client:
            mock_resp = MagicMock()
            mock_resp.status_code = 403
            mock_client.return_value.__enter__ = MagicMock(return_value=mock_client.return_value)
            mock_client.return_value.__exit__ = MagicMock(return_value=False)
            mock_client.return_value.get.return_value = mock_resp
            result = watcher._check_repo_update("test/repo", MagicMock())
            assert result is False
