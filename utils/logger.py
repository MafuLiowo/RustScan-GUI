"""统一日志配置：控制台 + 滚动文件。"""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler

from config.settings import (
    APP_NAME,
    LOG_BACKUP_COUNT,
    LOG_FILE,
    LOG_MAX_BYTES,
    LOGS_DIR,
)

_configured = False


def setup_logging(level: int = logging.INFO) -> logging.Logger:
    """初始化应用日志器；重复调用不会重复挂载 handler。"""
    global _configured
    logger = logging.getLogger(APP_NAME)
    if _configured:
        return logger

    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    console = logging.StreamHandler()
    console.setFormatter(formatter)

    file_handler = RotatingFileHandler(
        LOG_FILE,
        maxBytes=LOG_MAX_BYTES,
        backupCount=LOG_BACKUP_COUNT,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)

    logger.setLevel(level)
    logger.addHandler(console)
    logger.addHandler(file_handler)
    logger.propagate = False
    _configured = True
    return logger