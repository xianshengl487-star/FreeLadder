"""FreeLadder Windows 打包脚本

使用方法:
    python tools/build_windows.py

打包后输出:
    dist/FreeLadder/FreeLadder.exe
    dist/FreeLadder/FreeLadder-Console.exe (可选)

注意:
    - 使用 PyInstaller onedir 模式
    - 不会自动打包 Mihomo 二进制文件
    - 不会自动打包 Playwright Chromium
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

# Windows GBK 编码兼容
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass


def clean_build(root: Path):
    """清理构建目录"""
    for d in ["build", "dist"]:
        p = root / d
        if p.exists():
            print(f"清理 {p}")
            shutil.rmtree(p, ignore_errors=True)


def build_exe(root: Path, console: bool = False):
    """执行 PyInstaller 打包"""
    name = "FreeLadder-Console" if console else "FreeLadder"
    mode = "--console" if console else "--windowed"

    cmd = [
        sys.executable,
        "-m", "PyInstaller",
        "--noconfirm",
        "--clean",
        "--onedir",
        mode,
        "--name", name,
        f"--distpath={root / 'dist'}",
        f"--workpath={root / 'build'}",
        f"--specpath={root}",
        # 添加数据文件
        "--add-data", f"{root / 'config.example.yaml'};.",
        # 隐藏导入
        "--hidden-import", "uvicorn",
        "--hidden-import", "uvicorn.logging",
        "--hidden-import", "uvicorn.loops",
        "--hidden-import", "uvicorn.loops.auto",
        "--hidden-import", "uvicorn.protocols",
        "--hidden-import", "uvicorn.protocols.http",
        "--hidden-import", "uvicorn.protocols.http.auto",
        "--hidden-import", "uvicorn.protocols.websockets",
        "--hidden-import", "uvicorn.protocols.websockets.auto",
        "--hidden-import", "playwright",
        "--hidden-import", "playwright.async_api",
        "--hidden-import", "customtkinter",
        "--hidden-import", "freeladder",
        "--hidden-import", "freeladder.core",
        "--hidden-import", "freeladder.scraper",
        "--hidden-import", "freeladder.tester",
        "--hidden-import", "freeladder.exporter",
        "--hidden-import", "freeladder.gui",
        "--hidden-import", "freeladder.web",
        "--hidden-import", "freeladder.cli",
        "--hidden-import", "freeladder.browser",
        # 入口文件
        str(root / "freeladder" / "app_launcher.py"),
    ]

    print(f"\n打包 {name}...")
    print(f"命令: {' '.join(cmd)}\n")

    result = subprocess.run(cmd, cwd=str(root))
    if result.returncode != 0:
        print(f"✗ {name} 打包失败")
        return False

    print(f"✓ {name} 打包成功")
    return True


def copy_package_files(root: Path, console: bool = False):
    """复制软件包文件到 dist/FreeLadder"""
    dist_dir = root / "dist" / "FreeLadder"
    if not dist_dir.exists():
        print("✗ dist/FreeLadder 不存在，打包可能失败")
        return

    # 创建目录
    for d in ["bin", "data", "exports", "logs", "tools"]:
        (dist_dir / d).mkdir(parents=True, exist_ok=True)

    # 创建 .gitkeep
    for d in ["data", "exports", "logs"]:
        gitkeep = dist_dir / d / ".gitkeep"
        if not gitkeep.exists():
            gitkeep.write_text("")

    # 显式复制 config.example.yaml 到根目录
    config_example = root / "config.example.yaml"
    if config_example.exists():
        shutil.copy2(config_example, dist_dir / "config.example.yaml")
        print("  + config.example.yaml")
    else:
        print("⚠ config.example.yaml 不存在")

    # 复制 FreeLadder-Console.exe 到主包根目录
    console_dir = root / "dist" / "FreeLadder-Console"
    console_exe = console_dir / "FreeLadder-Console.exe"
    if console_exe.exists():
        shutil.copy2(console_exe, dist_dir / "FreeLadder-Console.exe")
        print("  + FreeLadder-Console.exe (copied to main package)")
    else:
        print("⚠ 未找到 FreeLadder-Console.exe，check_env.bat 可能不可用")

    # 复制 .bat 文件
    tools_src = root / "tools"
    tools_dst = dist_dir / "tools"

    bat_files = [
        "install_playwright_chromium.bat",
        "check_env.bat",
        "open_config.bat",
        "START.bat",
    ]
    for bf in bat_files:
        src = tools_src / bf
        if src.exists():
            shutil.copy2(src, tools_dst / bf)

    # 复制 README 文件
    for readme_name in ["README_PACKAGE.txt", "README_MIHOMO.txt"]:
        src = tools_src / readme_name
        if src.exists():
            shutil.copy2(src, tools_dst / readme_name)

    # 复制 START.bat 到根目录（方便用户双击）
    start_bat = tools_src / "START.bat"
    if start_bat.exists():
        shutil.copy2(start_bat, dist_dir / "START.bat")

    # 复制 README_MIHOMO.txt 到 bin/
    readme_mihomo = tools_src / "README_MIHOMO.txt"
    if readme_mihomo.exists():
        shutil.copy2(readme_mihomo, dist_dir / "bin" / "README_MIHOMO.txt")

    # 复制 Mihomo 二进制（若已下载到 bin/）
    mihomo_src = root / "bin" / "mihomo.exe"
    if mihomo_src.exists():
        shutil.copy2(mihomo_src, dist_dir / "bin" / "mihomo.exe")
        print("  + bin/mihomo.exe")

    print("✓ 软件包文件已复制")


def build():
    """完整打包流程"""
    root = Path(__file__).parent.parent

    print("=" * 60)
    print("FreeLadder Windows 打包脚本")
    print("=" * 60)
    print(f"项目目录: {root}")
    print(f"入口文件: freeladder/app_launcher.py")
    print(f"输出目录: {root / 'dist' / 'FreeLadder'}")
    print()

    # 清理
    clean_build(root)

    # 打包 GUI 版
    if not build_exe(root, console=False):
        return

    # 打包 Console 版（可选）
    build_exe(root, console=True)

    # 复制软件包文件
    copy_package_files(root)

    print()
    print("=" * 60)
    print("✓ 打包完成！")
    print(f"  输出目录: {root / 'dist' / 'FreeLadder'}")
    print(f"  GUI 版:   {root / 'dist' / 'FreeLadder' / 'FreeLadder.exe'}")
    print(f"  调试版:   {root / 'dist' / 'FreeLadder' / 'FreeLadder-Console.exe'}")
    print()
    print("使用前请将 Mihomo 二进制文件放入:")
    print(f"  {root / 'dist' / 'FreeLadder' / 'bin'}")
    print("=" * 60)


if __name__ == "__main__":
    build()
