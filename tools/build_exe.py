# path: tools/build_exe.py
"""PyInstaller 打包脚本

使用方法:
    python tools/build_exe.py

打包后输出:
    dist/FreeLadder/FreeLadder.exe

注意:
    - 默认打包为 onedir 模式
    - 不会自动打包 Mihomo 二进制文件
    - 请手动将 Mihomo 放到 bin/ 目录
"""

import subprocess
import sys
from pathlib import Path


def build():
    """执行打包"""
    root = Path(__file__).parent.parent

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--name", "FreeLadder",
        "--onedir",
        "--windowed",
        "--noconfirm",
        # 添加数据文件
        "--add-data", f"{root / 'config.example.yaml'};.",
        # 添加隐藏导入
        "--hidden-import", "freeladder",
        "--hidden-import", "freeladder.core",
        "--hidden-import", "freeladder.scraper",
        "--hidden-import", "freeladder.tester",
        "--hidden-import", "freeladder.exporter",
        "--hidden-import", "freeladder.gui",
        "--hidden-import", "freeladder.web",
        "--hidden-import", "freeladder.cli",
        # 入口文件
        str(root / "run_gui.py"),
    ]

    print("=" * 60)
    print("FreeLadder 打包脚本")
    print("=" * 60)
    print(f"项目目录: {root}")
    print(f"入口文件: run_gui.py")
    print(f"输出目录: {root / 'dist' / 'FreeLadder'}")
    print()

    print("执行命令:")
    print(" ".join(cmd))
    print()

    result = subprocess.run(cmd, cwd=str(root))

    if result.returncode == 0:
        print()
        print("=" * 60)
        print("✓ 打包成功！")
        print(f"  输出目录: {root / 'dist' / 'FreeLadder'}")
        print(f"  可执行文件: {root / 'dist' / 'FreeLadder' / 'FreeLadder.exe'}")
        print()
        print("使用前请将 Mihomo 二进制文件放入:")
        print(f"  {root / 'dist' / 'FreeLadder' / 'bin'}")
        print("=" * 60)
    else:
        print()
        print("✗ 打包失败，请检查错误信息")


if __name__ == "__main__":
    build()
