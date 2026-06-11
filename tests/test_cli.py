# path: tests/test_cli.py
"""CLI 模块测试 - 匹配实际 CLI 命令"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from freeladder.cli.main import cli
from freeladder.core.models import Protocol
from tests.conftest import make_node


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def mock_db():
    with patch("freeladder.cli.main.get_db") as mock:
        db = MagicMock()
        mock.return_value = db
        yield db


@pytest.fixture
def mock_config(tmp_path):
    from freeladder.core.config import Config, AppConfig
    cfg = Config(app=AppConfig(data_dir=str(tmp_path)))
    with patch("freeladder.cli.main.get_config", return_value=cfg):
        yield cfg


class TestCLIMain:
    def test_main_help(self, runner):
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "FreeLadder" in result.output

    def test_list_help(self, runner):
        result = runner.invoke(cli, ["list", "--help"])
        assert result.exit_code == 0

    def test_fetch_help(self, runner):
        result = runner.invoke(cli, ["fetch", "--help"])
        assert result.exit_code == 0

    def test_export_help(self, runner):
        result = runner.invoke(cli, ["export", "--help"])
        assert result.exit_code == 0

    def test_test_help(self, runner):
        result = runner.invoke(cli, ["test", "--help"])
        assert result.exit_code == 0

    def test_stats_help(self, runner):
        result = runner.invoke(cli, ["stats", "--help"])
        assert result.exit_code == 0

    def test_ip_help(self, runner):
        result = runner.invoke(cli, ["ip", "--help"])
        assert result.exit_code == 0


class TestCLIList:
    def test_list_empty(self, runner, mock_db):
        mock_db.get_all_nodes.return_value = []
        result = runner.invoke(cli, ["list"])
        assert result.exit_code == 0

    def test_list_with_nodes(self, runner, mock_db):
        nodes = [make_node(protocol=Protocol.VMESS, server=f"10.0.0.{i}") for i in range(5)]
        mock_db.get_all_nodes.return_value = nodes
        result = runner.invoke(cli, ["list"])
        assert result.exit_code == 0

    def test_list_alive(self, runner, mock_db):
        nodes = [make_node(alive=True)]
        mock_db.get_alive_nodes.return_value = nodes
        result = runner.invoke(cli, ["list", "--alive"])
        assert result.exit_code == 0

    def test_list_limit(self, runner, mock_db):
        nodes = [make_node(protocol=Protocol.VMESS, server=f"10.0.0.{i}") for i in range(10)]
        mock_db.get_all_nodes.return_value = nodes
        result = runner.invoke(cli, ["list", "--limit", "3"])
        assert result.exit_code == 0

    def test_list_filter_protocol(self, runner, mock_db):
        nodes = [make_node(protocol=Protocol.VMESS)]
        mock_db.get_all_nodes.return_value = nodes
        result = runner.invoke(cli, ["list", "--protocol", "vmess"])
        assert result.exit_code == 0


class TestCLIFetch:
    def test_fetch_runs(self, runner, mock_db, mock_config):
        result = runner.invoke(cli, ["fetch"])
        assert result.exit_code == 0


class TestCLIExport:
    def test_export_runs(self, runner, mock_db, mock_config):
        result = runner.invoke(cli, ["export"])
        assert result.exit_code == 0
