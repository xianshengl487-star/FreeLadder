# path: freeladder/core/logger.py
"""日志系统模块"""

import sys
from loguru import logger


def setup_logger(level: str = "INFO", log_file: str = None):
    """配置日志系统"""
    # 移除默认处理器
    logger.remove()

    # 控制台输出
    logger.add(
        sys.stderr,
        level=level,
        format="<green>{time:HH:mm:ss}</green> | <level>{level:<8}</level> | <cyan>{name}</cyan> - {message}",
        colorize=True,
    )

    # 文件输出
    if log_file:
        logger.add(
            log_file,
            level=level,
            format="{time:YYYY-MM-DD HH:mm:ss} | {level:<8} | {name} - {message}",
            rotation="10 MB",
            retention="7 days",
        )

    return logger
