"""tests/test_runtime_check.py - 运行时检查模块测试"""

from pathlib import Path

from freeladder.runtime_check import (
    RuntimeCheckResult,
    check_chromium,
    check_mihomo,
    check_playwright,
    ensure_runtime_dirs,
    format_check_result,
    get_runtime_root,
    is_frozen,
)


def test_is_frozen_returns_bool():
    """is_frozen 应返回布尔值"""
    result = is_frozen()
    assert isinstance(result, bool)


def test_get_runtime_root_returns_path():
    """get_runtime_root 应返回 Path"""
    root = get_runtime_root()
    assert isinstance(root, Path)
    assert root.exists()


def test_get_runtime_root_source_mode():
    """源码模式下 get_runtime_root 应返回项目根目录"""
    import os
    # 确保环境变量未设置
    old_val = os.environ.pop("FREELADDER_RUNTIME_ROOT", None)
    try:
        root = get_runtime_root()
        # 应该包含 freeladder 目录
        assert (root / "freeladder").exists() or (root / "freeladder").is_dir()
    finally:
        if old_val is not None:
            os.environ["FREELADDER_RUNTIME_ROOT"] = old_val


def test_get_runtime_root_env_override():
    """环境变量应覆盖默认路径"""
    import os
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        os.environ["FREELADDER_RUNTIME_ROOT"] = tmpdir
        try:
            root = get_runtime_root()
            # 使用 resolve() 比较，避免 Windows 8.3 短路径名问题
            assert root.resolve() == Path(tmpdir).resolve()
        finally:
            del os.environ["FREELADDER_RUNTIME_ROOT"]


def test_ensure_runtime_dirs_creates_directories(tmp_path):
    """ensure_runtime_dirs 应创建必要目录"""
    result = ensure_runtime_dirs(tmp_path)

    assert result.ok
    assert (tmp_path / "data").exists()
    assert (tmp_path / "exports").exists()
    assert (tmp_path / "logs").exists()
    assert (tmp_path / "bin").exists()
    assert result.data_dir == tmp_path / "data"
    assert result.export_dir == tmp_path / "exports"
    assert result.log_dir == tmp_path / "logs"
    assert result.bin_dir == tmp_path / "bin"


def test_ensure_runtime_dirs_copies_config(tmp_path):
    """ensure_runtime_dirs 应在有 example 时创建 config.yaml"""
    # 创建 example
    example = tmp_path / "config.example.yaml"
    example.write_text("app:\n  name: Test\n", encoding="utf-8")

    result = ensure_runtime_dirs(tmp_path)

    assert result.ok
    assert result.config_exists
    assert (tmp_path / "config.yaml").exists()


def test_ensure_runtime_dirs_no_example(tmp_path):
    """没有 example 时不应崩溃"""
    result = ensure_runtime_dirs(tmp_path)
    assert result.ok
    assert not result.config_exists


def test_check_mihomo_not_found(tmp_path):
    """没有 mihomo 时应返回 False"""
    import os
    old_val = os.environ.pop("MIHOMO_PATH", None)
    try:
        found, msg = check_mihomo(tmp_path)
        assert not found
        assert "未找到" in msg or "MISSING" in msg.lower() or "mihomo" in msg.lower()
    finally:
        if old_val is not None:
            os.environ["MIHOMO_PATH"] = old_val


def test_check_playwright():
    """check_playwright 应返回 tuple"""
    found, msg = check_playwright()
    assert isinstance(found, bool)
    assert isinstance(msg, str)


def test_check_chromium_not_found(tmp_path):
    """没有 chromium 时应返回 False"""
    found, msg = check_chromium(tmp_path)
    assert not found


def test_format_check_result():
    """format_check_result 应返回可读字符串"""
    result = RuntimeCheckResult(
        ok=True,
        project_root=Path("/test"),
        data_dir=Path("/test/data"),
        export_dir=Path("/test/exports"),
        log_dir=Path("/test/logs"),
        bin_dir=Path("/test/bin"),
    )
    text = format_check_result(result)
    assert "FreeLadder Runtime Check" in text
    assert "Runtime root" in text
    assert "OK" in text
