# path: main.py
"""FreeLadder 主入口 - CLI 模式

用法:
    python main.py init          初始化
    python main.py update        更新节点
    python main.py test          测试节点
    python main.py list          列出节点
    python main.py export        导出配置
    python main.py web           启动 Web API
    python main.py gui           启动 GUI
    python main.py stats         显示统计
"""

import sys
import os

# Windows: 强制控制台使用 UTF-8，避免 click.echo 输出 Unicode 符号时 GBK 报错
if os.name == "nt":
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from freeladder.cli.main import main

if __name__ == "__main__":
    main()
