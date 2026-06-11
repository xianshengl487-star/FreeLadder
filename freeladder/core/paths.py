# path: freeladder/core/paths.py
"""路径管理模块 - 确定数据目录和导出目录"""

import os
import sys
from pathlib import Path


def get_project_root() -> Path:
    """获取项目根目录"""
    # 如果是 PyInstaller 打包的，使用 exe 所在目录
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).parent
    # 否则使用脚本所在目录向上一层到项目根
    return Path(__file__).resolve().parent.parent.parent


def get_data_dir(data_dir: str = "") -> Path:
    """获取数据目录"""
    if data_dir:
        p = Path(data_dir)
        p.mkdir(parents=True, exist_ok=True)
        return p

    root = get_project_root()
    data = root / "data"
    data.mkdir(parents=True, exist_ok=True)
    return data


def get_export_dir(export_dir: str = "") -> Path:
    """获取导出目录"""
    if export_dir:
        p = Path(export_dir)
        p.mkdir(parents=True, exist_ok=True)
        return p

    root = get_project_root()
    exports = root / "exports"
    exports.mkdir(parents=True, exist_ok=True)
    return exports


def get_bin_dir() -> Path:
    """获取二进制文件目录"""
    root = get_project_root()
    bindir = root / "bin"
    bindir.mkdir(parents=True, exist_ok=True)
    return bindir
