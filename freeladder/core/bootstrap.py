# path: freeladder/core/bootstrap.py
"""首次运行引导：确保内置免费源与分批获取配置已打包启用"""

from __future__ import annotations

from pathlib import Path

from loguru import logger


def ensure_bundled_defaults(config_path: Path) -> None:
    """确保配置文件包含软件内置的默认获取设置"""
    if not config_path.exists():
        return

    try:
        import yaml
        raw = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    except Exception:
        return

    changed = False
    scraper = raw.setdefault("scraper", {})

    if not scraper.get("builtin_enabled", False):
        scraper["builtin_enabled"] = True
        changed = True

    if "fetch_batch_sources" not in scraper:
        scraper["fetch_batch_sources"] = 10
        changed = True

    if "fetch_batch_max_nodes" not in scraper:
        scraper["fetch_batch_max_nodes"] = 1500
        changed = True

    gui = raw.setdefault("gui", {})
    if "country_search_enabled" not in gui:
        gui["country_search_enabled"] = True
        changed = True

    if changed:
        try:
            import yaml
            with open(config_path, "w", encoding="utf-8") as f:
                yaml.dump(raw, f, default_flow_style=False, allow_unicode=True)
            logger.info("已应用内置默认配置（builtin_enabled / 分批获取 / 国家搜索）")
        except OSError as e:
            logger.debug(f"写入默认配置失败: {e}")