"""FreeLadder 运行时检查模块

启动时检查运行环境，确保必要目录和配置存在。
不直接崩溃，只给出 warnings 和 errors。
"""

import os
import shutil
import sys
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class RuntimeCheckResult:
    """运行时检查结果"""
    ok: bool = True
    warnings: list = field(default_factory=list)
    errors: list = field(default_factory=list)
    project_root: Path = field(default_factory=Path)
    data_dir: Path = field(default_factory=Path)
    export_dir: Path = field(default_factory=Path)
    log_dir: Path = field(default_factory=Path)
    bin_dir: Path = field(default_factory=Path)
    config_exists: bool = False
    mihomo_found: bool = False
    mihomo_path: str = ""
    playwright_found: bool = False
    chromium_found: bool = False
    writable: bool = True
    is_frozen: bool = False


def is_frozen() -> bool:
    """判断是否为 PyInstaller frozen 环境"""
    return getattr(sys, 'frozen', False)


def get_runtime_root() -> Path:
    """
    获取运行时根目录。

    源码运行：返回项目根目录
    PyInstaller onedir：返回 exe 所在目录
    环境变量 FREELADDER_RUNTIME_ROOT 优先
    """
    env_root = os.environ.get("FREELADDER_RUNTIME_ROOT")
    if env_root:
        return Path(env_root).resolve()

    if is_frozen():
        return Path(sys.executable).resolve().parent

    return Path(__file__).resolve().parent.parent.parent


def ensure_runtime_dirs(root: Path = None) -> RuntimeCheckResult:
    """确保运行时必要目录存在"""
    if root is None:
        root = get_runtime_root()

    result = RuntimeCheckResult(project_root=root, is_frozen=is_frozen())

    # 创建必要目录
    for dir_name in ["data", "exports", "logs", "bin"]:
        dir_path = root / dir_name
        try:
            dir_path.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            result.errors.append(f"无法创建目录 {dir_name}/: {e}")
            result.ok = False

    result.data_dir = root / "data"
    result.export_dir = root / "exports"
    result.log_dir = root / "logs"
    result.bin_dir = root / "bin"

    # 检查 config.yaml
    config_path = root / "config.yaml"
    example_path = root / "config.example.yaml"

    if config_path.exists():
        result.config_exists = True
    elif example_path.exists():
        try:
            shutil.copy2(example_path, config_path)
            result.config_exists = True
        except OSError as e:
            result.errors.append(f"无法创建 config.yaml: {e}")
            result.ok = False
    else:
        result.warnings.append("config.yaml 和 config.example.yaml 均不存在")

    # 检查写入权限
    try:
        test_file = root / ".write_test"
        test_file.write_text("test")
        test_file.unlink()
    except OSError:
        result.warnings.append("项目根目录不可写")
        result.writable = False

    return result


def check_mihomo(root: Path = None) -> tuple:
    """检查 Mihomo 是否存在，返回 (found, path_or_message)"""
    if root is None:
        root = get_runtime_root()

    # 检查环境变量
    env_path = os.environ.get("MIHOMO_PATH")
    if env_path and Path(env_path).exists():
        return True, env_path

    # 检查 bin/ 目录
    bin_dir = root / "bin"
    for name in ["mihomo.exe", "mihomo", "clash-meta.exe", "clash-meta"]:
        p = bin_dir / name
        if p.exists():
            return True, str(p)

    return False, "Mihomo 未找到，请将 mihomo.exe 放入 bin/ 目录"


def check_playwright() -> tuple:
    """检查 Playwright 是否可导入"""
    try:
        import playwright  # noqa: F401
        return True, "Playwright 已安装"
    except ImportError:
        return False, "Playwright 未安装，请运行: pip install playwright"


def check_chromium(root: Path = None) -> tuple:
    """检查 Playwright Chromium 是否已安装"""
    if root is None:
        root = get_runtime_root()

    browsers_path = os.environ.get("PLAYWRIGHT_BROWSERS_PATH")
    if not browsers_path:
        browsers_path = str(root / "ms-playwright")

    pw_path = Path(browsers_path)
    if pw_path.exists():
        # 检查是否有 chromium 子目录
        for item in pw_path.iterdir():
            if "chromium" in item.name.lower():
                return True, str(item)

    return False, "Chromium 未安装，请运行 tools/install_playwright_chromium.bat"


def run_runtime_check() -> RuntimeCheckResult:
    """执行完整运行时检查"""
    root = get_runtime_root()
    result = ensure_runtime_dirs(root)

    # 检查 Mihomo
    mihomo_found, mihomo_msg = check_mihomo(root)
    result.mihomo_found = mihomo_found
    result.mihomo_path = mihomo_msg if mihomo_found else ""
    if not mihomo_found:
        result.warnings.append(mihomo_msg)

    # 检查 Playwright
    pw_found, pw_msg = check_playwright()
    result.playwright_found = pw_found
    if not pw_found:
        result.warnings.append(pw_msg)

    # 检查 Chromium
    cr_found, cr_msg = check_chromium(root)
    result.chromium_found = cr_found
    if not cr_found:
        result.warnings.append(cr_msg)

    return result


def format_check_result(result: RuntimeCheckResult) -> str:
    """格式化检查结果为可读字符串"""
    lines = [
        "FreeLadder Runtime Check",
        "=" * 40,
        f"Runtime root: {result.project_root}",
        f"Frozen: {'Yes' if result.is_frozen else 'No'}",
        f"Config: {'OK' if result.config_exists else 'MISSING'}",
        f"Data dir: {'OK' if result.data_dir.exists() else 'MISSING'}",
        f"Exports dir: {'OK' if result.export_dir.exists() else 'MISSING'}",
        f"Logs dir: {'OK' if result.log_dir.exists() else 'MISSING'}",
        f"Bin dir: {'OK' if result.bin_dir.exists() else 'MISSING'}",
        f"Mihomo: {'FOUND' if result.mihomo_found else 'MISSING'}",
        f"Playwright: {'FOUND' if result.playwright_found else 'MISSING'}",
        f"Chromium: {'FOUND' if result.chromium_found else 'MISSING'}",
        f"Writable: {'OK' if result.writable else 'NO'}",
    ]

    if result.warnings:
        lines.append("")
        lines.append("Warnings:")
        for w in result.warnings:
            lines.append(f"  - {w}")

    if result.errors:
        lines.append("")
        lines.append("Errors:")
        for e in result.errors:
            lines.append(f"  - {e}")

    return "\n".join(lines)
