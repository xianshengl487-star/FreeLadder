# path: freeladder/core/config.py
"""配置管理模块"""

import shutil
from pathlib import Path
from typing import Any, Optional

import yaml
from pydantic import BaseModel, Field

from .paths import get_project_root, get_data_dir, get_export_dir


class AppConfig(BaseModel):
    name: str = "FreeLadder"
    data_dir: str = ""
    export_dir: str = ""
    log_level: str = "INFO"


class ScraperConfig(BaseModel):
    sources: list[str] = Field(default_factory=list)
    request_timeout: int = 10
    max_workers: int = 6
    max_nodes_per_source: int = 800
    max_total_nodes: int = 8000
    source_failure_cache_minutes: int = 60
    builtin_enabled: bool = True


class TesterConfig(BaseModel):
    test_url: str = "https://www.gstatic.com/generate_204"
    timeout: int = 8
    max_workers: int = 20
    prefer_mihomo: bool = True
    tcp_fallback: bool = True


class MihomoConfig(BaseModel):
    binary_path: str = ""
    external_controller_host: str = "127.0.0.1"
    external_controller_port: int = 0
    mixed_port: int = 0
    secret: str = ""
    startup_timeout: int = 10


class WebConfig(BaseModel):
    host: str = "127.0.0.1"
    port: int = 8765


class GUIConfig(BaseModel):
    auto_update: bool = False
    update_interval_minutes: int = 120
    table_page_size: int = 200
    max_render_rows: int = 300
    progress_update_interval_ms: int = 500


class BrowserConfig(BaseModel):
    enabled: bool = True
    engine: str = "playwright"
    headless: bool = False
    isolate_profile: bool = True
    profile_dir: str = "data/browser_profiles"
    cleanup_profile_on_close: bool = False
    default_url: str = "https://www.google.com"
    control_api_host: str = "127.0.0.1"
    control_api_port: int = 8787
    allow_external_control: bool = True
    extension_dirs: list[str] = Field(default_factory=list)
    ai_control_enabled: bool = True


class SourceIntelConfig(BaseModel):
    """源情报引擎配置"""
    enabled: bool = True

    # GitHub 项目监控
    github_watch_enabled: bool = True
    github_token: str = ""
    github_account_watch_enabled: bool = False
    github_check_interval_minutes: int = 360
    github_max_repos_per_run: int = 20
    github_use_etag: bool = True
    github_follow_with_account: bool = False

    # 非 GitHub 公开源发现
    non_github_discovery_enabled: bool = True
    non_github_check_interval_minutes: int = 720
    max_sites_per_run: int = 20
    max_links_per_site: int = 50
    max_depth_per_site: int = 0

    # RSS / Atom
    rss_watch_enabled: bool = True
    rss_check_interval_minutes: int = 720

    # 源验证
    validate_before_enable: bool = True
    min_nodes_to_accept: int = 1
    max_download_mb: int = 5
    max_nodes_per_source: int = 800
    max_total_nodes: int = 8000
    request_timeout_seconds: int = 15
    user_agent: str = "FreeLadder SourceIntel/1.0"

    # 失败缓存
    failure_cache_minutes: int = 60
    stale_source_days: int = 7
    remove_dead_after_failures: int = 5

    # 自动刷新
    auto_refresh_sources: bool = True
    auto_refresh_nodes: bool = False
    auto_test_after_refresh: bool = False
    auto_export_after_refresh: bool = False

    # 安全确认
    require_user_confirm_for_new_sources: bool = True
    require_user_confirm_for_github_account_watch: bool = True


class Config(BaseModel):
    app: AppConfig = Field(default_factory=AppConfig)
    scraper: ScraperConfig = Field(default_factory=ScraperConfig)
    tester: TesterConfig = Field(default_factory=TesterConfig)
    mihomo: MihomoConfig = Field(default_factory=MihomoConfig)
    web: WebConfig = Field(default_factory=WebConfig)
    gui: GUIConfig = Field(default_factory=GUIConfig)
    browser: BrowserConfig = Field(default_factory=BrowserConfig)
    source_intel: SourceIntelConfig = Field(default_factory=SourceIntelConfig)

    @property
    def data_path(self) -> Path:
        return get_data_dir(self.app.data_dir)

    @property
    def export_path(self) -> Path:
        return get_export_dir(self.app.export_dir)


_config: Optional[Config] = None


def load_config(config_path: Optional[Path] = None) -> Config:
    """从 YAML 文件加载配置"""
    global _config

    if config_path is None:
        config_path = get_project_root() / "config.yaml"

    example_path = get_project_root() / "config.example.yaml"

    if not config_path.exists():
        if example_path.exists():
            shutil.copy2(example_path, config_path)
        else:
            _config = Config()
            return _config

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}
    except Exception:
        raw = {}

    _config = Config(**raw)
    return _config


def save_config(config: Config, config_path: Optional[Path] = None):
    """保存配置到 YAML 文件"""
    if config_path is None:
        config_path = get_project_root() / "config.yaml"

    data = config.model_dump()
    with open(config_path, "w", encoding="utf-8") as f:
        yaml.dump(data, f, default_flow_style=False, allow_unicode=True)


def get_config() -> Config:
    """获取全局配置实例"""
    global _config
    if _config is None:
        _config = load_config()
    return _config
