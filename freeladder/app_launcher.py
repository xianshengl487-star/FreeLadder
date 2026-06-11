"""FreeLadder 统一启动入口

作为 EXE 入口，负责：
1. 运行时检查
2. 自动创建必要目录和配置
3. 设置环境变量
4. 启动 GUI 或执行 CLI 命令
"""

import argparse
import os
import sys
import traceback
from pathlib import Path


def setup_runtime_environment(result):
    """设置运行时环境变量"""
    os.environ.setdefault(
        "FREELADDER_RUNTIME_ROOT",
        str(result.project_root),
    )
    os.environ.setdefault(
        "PLAYWRIGHT_BROWSERS_PATH",
        str(result.project_root / "ms-playwright"),
    )


def launch_gui():
    """启动 GUI"""
    try:
        from freeladder.core.config import load_config
        from freeladder.core.logger import setup_logger
        load_config()
        setup_logger("INFO")

        from freeladder.gui.app import FreeLadderApp

        app = FreeLadderApp()
        app.protocol("WM_DELETE_WINDOW", app.on_closing)
        app.mainloop()
    except Exception as e:
        error_log = Path(os.environ.get(
            "FREELADDER_RUNTIME_ROOT", "."
        )) / "logs" / "startup_error.log"
        error_log.parent.mkdir(parents=True, exist_ok=True)
        with open(error_log, "a", encoding="utf-8") as f:
            f.write(f"=== Startup Error ===\n")
            f.write(f"{e}\n")
            f.write(traceback.format_exc())
            f.write("\n")
        print(f"GUI 启动失败: {e}", file=sys.stderr)
        print(f"错误日志: {error_log}", file=sys.stderr)


def print_runtime_check():
    """打印运行时检查结果"""
    from freeladder.runtime_check import run_runtime_check, format_check_result
    result = run_runtime_check()
    print(format_check_result(result))


def main():
    """统一入口"""
    parser = argparse.ArgumentParser(description="FreeLadder")
    parser.add_argument(
        "--runtime-check",
        action="store_true",
        help="执行运行时检查并退出",
    )
    parser.parse_args()

    if "--runtime-check" in sys.argv:
        print_runtime_check()
        return

    # 运行时检查
    from freeladder.runtime_check import run_runtime_check
    result = run_runtime_check()

    # 设置环境
    setup_runtime_environment(result)

    # 启动 GUI
    launch_gui()


if __name__ == "__main__":
    main()
