# path: run_gui.py
"""FreeLadder GUI 启动入口"""

import sys
from pathlib import Path

# 确保项目根目录在 Python 路径中
root = Path(__file__).parent
if str(root) not in sys.path:
    sys.path.insert(0, str(root))

from freeladder.core.config import load_config
from freeladder.core.logger import setup_logger

# 加载配置
load_config()
cfg = setup_logger("INFO")

from freeladder.gui.app import FreeLadderApp

if __name__ == "__main__":
    app = FreeLadderApp()
    app.protocol("WM_DELETE_WINDOW", app.on_closing)
    app.mainloop()
