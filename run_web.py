# path: run_web.py
"""FreeLadder Web API 启动入口"""

import sys
from pathlib import Path

# 确保项目根目录在 Python 路径中
root = Path(__file__).parent
if str(root) not in sys.path:
    sys.path.insert(0, str(root))

from freeladder.core.config import load_config, get_config
from freeladder.core.logger import setup_logger

# 加载配置
load_config()
cfg = get_config()
setup_logger(cfg.app.log_level)

import uvicorn
from freeladder.web.api import create_app

if __name__ == "__main__":
    app = create_app()
    print(f"FreeLadder Web API: http://{cfg.web.host}:{cfg.web.port}")
    uvicorn.run(app, host=cfg.web.host, port=cfg.web.port, log_level="info")
