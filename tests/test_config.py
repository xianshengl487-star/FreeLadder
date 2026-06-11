# path: tests/test_config.py
"""配置管理模块测试"""

import tempfile
from pathlib import Path

import pytest
import yaml

from freeladder.core.config import (
    AppConfig,
    BrowserConfig,
    Config,
    GUIConfig,
    MihomoConfig,
    ScraperConfig,
    TesterConfig,
    WebConfig,
    load_config,
    save_config,
)


class TestAppConfig:
    def test_default_values(self):
        cfg = AppConfig()
        assert cfg.name == "FreeLadder"
        assert cfg.data_dir == ""
        assert cfg.export_dir == ""
        assert cfg.log_level == "INFO"

    def test_custom_values(self):
        cfg = AppConfig(name="Test", data_dir="/tmp", export_dir="/out", log_level="DEBUG")
        assert cfg.name == "Test"
        assert cfg.data_dir == "/tmp"
        assert cfg.log_level == "DEBUG"


class TestScraperConfig:
    def test_default_values(self):
        cfg = ScraperConfig()
        assert cfg.sources == []
        assert cfg.request_timeout == 10
        assert cfg.max_workers == 6
        assert cfg.max_nodes_per_source == 800
        assert cfg.max_total_nodes == 8000
        assert cfg.source_failure_cache_minutes == 60
        assert cfg.builtin_enabled is True

    def test_custom_sources(self):
        cfg = ScraperConfig(sources=["http://example.com/sub1", "http://example.com/sub2"])
        assert len(cfg.sources) == 2


class TestTesterConfig:
    def test_default_values(self):
        cfg = TesterConfig()
        assert cfg.test_url == "https://www.gstatic.com/generate_204"
        assert cfg.timeout == 8
        assert cfg.max_workers == 20
        assert cfg.prefer_mihomo is True
        assert cfg.tcp_fallback is True


class TestMihomoConfig:
    def test_default_values(self):
        cfg = MihomoConfig()
        assert cfg.binary_path == ""
        assert cfg.external_controller_host == "127.0.0.1"
        assert cfg.external_controller_port == 0


class TestWebConfig:
    def test_default_values(self):
        cfg = WebConfig()
        assert cfg.host == "127.0.0.1"
        assert cfg.port == 8765


class TestGUIConfig:
    def test_default_values(self):
        cfg = GUIConfig()
        assert cfg.auto_update is False
        assert cfg.update_interval_minutes == 120
        assert cfg.table_page_size == 200
        assert cfg.max_render_rows == 300
        assert cfg.progress_update_interval_ms == 500

    def test_custom_values(self):
        cfg = GUIConfig(table_page_size=100, max_render_rows=150, progress_update_interval_ms=200)
        assert cfg.table_page_size == 100
        assert cfg.max_render_rows == 150
        assert cfg.progress_update_interval_ms == 200


class TestBrowserConfig:
    def test_default_values(self):
        cfg = BrowserConfig()
        assert cfg.enabled is True
        assert cfg.engine == "playwright"
        assert cfg.headless is False


class TestConfig:
    def test_default_factory(self):
        cfg = Config()
        assert isinstance(cfg.app, AppConfig)
        assert isinstance(cfg.scraper, ScraperConfig)
        assert isinstance(cfg.tester, TesterConfig)
        assert isinstance(cfg.mihomo, MihomoConfig)
        assert isinstance(cfg.web, WebConfig)
        assert isinstance(cfg.gui, GUIConfig)
        assert isinstance(cfg.browser, BrowserConfig)

    def test_custom_config(self):
        cfg = Config(
            app=AppConfig(name="Test"),
            scraper=ScraperConfig(request_timeout=5),
            gui=GUIConfig(table_page_size=50),
        )
        assert cfg.app.name == "Test"
        assert cfg.scraper.request_timeout == 5
        assert cfg.gui.table_page_size == 50

    def test_data_path(self, monkeypatch):
        monkeypatch.setattr(
            "freeladder.core.config.get_data_dir",
            lambda x: Path("/fake/data"),
        )
        cfg = Config(app=AppConfig(data_dir="/custom"))
        assert cfg.data_path == Path("/fake/data")

    def test_export_path(self, monkeypatch):
        monkeypatch.setattr(
            "freeladder.core.config.get_export_dir",
            lambda x: Path("/fake/export"),
        )
        cfg = Config(app=AppConfig(export_dir="/custom"))
        assert cfg.export_path == Path("/fake/export")

    def test_to_dict(self):
        cfg = Config()
        d = cfg.model_dump()
        assert "app" in d
        assert "scraper" in d
        assert "tester" in d
        assert "gui" in d
        assert d["gui"]["table_page_size"] == 200


class TestLoadConfig:
    def test_load_from_yaml(self, tmp_path):
        config_data = {
            "app": {"name": "TestApp", "log_level": "DEBUG"},
            "scraper": {"request_timeout": 5, "sources": ["http://test.com"]},
            "gui": {"table_page_size": 100},
        }
        config_path = tmp_path / "config.yaml"
        config_path.write_text(yaml.dump(config_data), encoding="utf-8")

        cfg = load_config(config_path)
        assert cfg.app.name == "TestApp"
        assert cfg.scraper.request_timeout == 5
        assert cfg.gui.table_page_size == 100

    def test_load_empty_yaml(self, tmp_path):
        config_path = tmp_path / "config.yaml"
        config_path.write_text("", encoding="utf-8")
        cfg = load_config(config_path)
        assert cfg.app.name == "FreeLadder"

    def test_load_invalid_yaml(self, tmp_path):
        config_path = tmp_path / "config.yaml"
        config_path.write_text("{{invalid yaml}}", encoding="utf-8")
        cfg = load_config(config_path)
        assert cfg.app.name == "FreeLadder"


class TestSaveConfig:
    def test_save_and_reload(self, tmp_path):
        config_path = tmp_path / "config.yaml"
        original = Config(
            app=AppConfig(name="SaveTest"),
            scraper=ScraperConfig(request_timeout=7),
        )
        save_config(original, config_path)
        assert config_path.exists()

        reloaded = load_config(config_path)
        assert reloaded.app.name == "SaveTest"
        assert reloaded.scraper.request_timeout == 7

    def test_save_preserves_gui_fields(self, tmp_path):
        config_path = tmp_path / "config.yaml"
        cfg = Config(
            gui=GUIConfig(table_page_size=50, max_render_rows=100, progress_update_interval_ms=200),
        )
        save_config(cfg, config_path)

        reloaded = load_config(config_path)
        assert reloaded.gui.table_page_size == 50
        assert reloaded.gui.max_render_rows == 100
        assert reloaded.gui.progress_update_interval_ms == 200
