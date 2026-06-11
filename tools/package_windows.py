"""FreeLadder Windows 打包并生成 zip

使用方法:
    python tools/package_windows.py
    python tools/package_windows.py --include-chromium

输出:
    release/FreeLadder-Windows-Portable-v{version}.zip
"""

import argparse
import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

# Windows GBK 编码兼容
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

# 版本号
VERSION = "0.1.0"


def get_version(root: Path) -> str:
    """从 freeladder/__init__.py 读取版本号"""
    init_file = root / "freeladder" / "__init__.py"
    if init_file.exists():
        content = init_file.read_text(encoding="utf-8")
        for line in content.splitlines():
            if line.startswith("__version__"):
                return line.split("=")[1].strip().strip('"').strip("'")
    return VERSION


def build_package(root: Path):
    """调用 build_windows.py"""
    result = subprocess.run(
        [sys.executable, str(root / "tools" / "build_windows.py")],
        cwd=str(root),
    )
    return result.returncode == 0


def install_chromium(root: Path):
    """安装 Playwright Chromium 到 dist/FreeLadder/ms-playwright"""
    dist_dir = root / "dist" / "FreeLadder"
    pw_dir = dist_dir / "ms-playwright"

    print(f"\n安装 Playwright Chromium 到 {pw_dir}...")

    env = os.environ.copy()
    env["PLAYWRIGHT_BROWSERS_PATH"] = str(pw_dir)

    result = subprocess.run(
        [sys.executable, "-m", "playwright", "install", "chromium"],
        cwd=str(root),
        env=env,
    )

    if result.returncode == 0:
        print("✓ Chromium 安装成功")
    else:
        print("✗ Chromium 安装失败")
        print("  请确保已安装: pip install playwright && playwright install chromium")

    return result.returncode == 0


def create_zip(root: Path, version: str):
    """生成 zip 包"""
    dist_dir = root / "dist" / "FreeLadder"
    release_dir = root / "release"
    release_dir.mkdir(parents=True, exist_ok=True)

    zip_name = f"FreeLadder-Windows-Portable-v{version}.zip"
    zip_path = release_dir / zip_name

    print(f"\n生成 zip: {zip_path}")

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for item in sorted(dist_dir.rglob("*")):
            if item.is_file():
                arcname = f"FreeLadder/{item.relative_to(dist_dir)}"
                zf.write(item, arcname)
                print(f"  + {arcname}")

    size_mb = zip_path.stat().st_size / (1024 * 1024)
    print(f"\n✓ zip 生成完成: {zip_path} ({size_mb:.1f} MB)")
    return zip_path


def main():
    parser = argparse.ArgumentParser(description="FreeLadder Windows 打包")
    parser.add_argument(
        "--include-chromium",
        action="store_true",
        help="在软件包中包含 Playwright Chromium",
    )
    args = parser.parse_args()

    root = Path(__file__).parent.parent

    print("=" * 60)
    print("FreeLadder Windows 打包脚本")
    print("=" * 60)

    # 获取版本号
    version = get_version(root)
    print(f"版本: {version}")

    # 检查 dist/FreeLadder
    dist_dir = root / "dist" / "FreeLadder"
    if not dist_dir.exists():
        print("\ndist/FreeLadder 不存在，开始打包...")
        if not build_package(root):
            print("✗ 打包失败")
            return

    if not dist_dir.exists():
        print("✗ dist/FreeLadder 不存在，打包失败")
        return

    # 安装 Chromium（可选）
    if args.include_chromium:
        install_chromium(root)

    # 生成 zip
    zip_path = create_zip(root, version)

    print()
    print("=" * 60)
    print("✓ 完成！")
    print(f"  软件包: {dist_dir}")
    print(f"  zip:    {zip_path}")
    print("=" * 60)


if __name__ == "__main__":
    main()
