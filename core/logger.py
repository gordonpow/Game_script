"""
統一日誌管理系統 (Logger)
支援同時輸出到 Console、Log 檔案 (logs/gamescript.log) 以及 GUI 即時監控面板
"""
from __future__ import annotations
import os
import sys
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

import ui.qt_compat
from PyQt6.QtCore import QObject, pyqtSignal

LOG_DIR = Path(__file__).parent.parent / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOG_DIR / "gamescript.log"


class QtLogEmitter(QObject):
    """將 Log 派發到 Qt UI 執行緒的信號橋接器"""
    new_log = pyqtSignal(str, str)  # (formatted_message, level)


# 全域單例
log_emitter = QtLogEmitter()


class QtLogHandler(logging.Handler):
    """自訂 logging Handler，轉發至 Qt Signal"""
    def emit(self, record):
        try:
            msg = self.format(record)
            log_emitter.new_log.emit(msg, record.levelname)
        except Exception:
            pass


# 建立統一 Logger
_logger = logging.getLogger("GameScript")
_logger.setLevel(logging.DEBUG)

if not _logger.handlers:
    # 格式化
    formatter = logging.Formatter(
        "[%(asctime)s.%(msecs)03d] [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S"
    )

    # 1. Console 輸出
    c_handler = logging.StreamHandler(sys.stdout)
    c_handler.setLevel(logging.DEBUG)
    c_handler.setFormatter(formatter)
    _logger.addHandler(c_handler)

    # 2. 檔案輸出 (UTF-8)
    f_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
    f_handler.setLevel(logging.DEBUG)
    f_handler.setFormatter(formatter)
    _logger.addHandler(f_handler)

    # 3. Qt 介面輸出
    q_handler = QtLogHandler()
    q_handler.setLevel(logging.DEBUG)
    q_handler.setFormatter(formatter)
    _logger.addHandler(q_handler)


def get_logger():
    return _logger


def log_info(msg: str):
    _logger.info(msg)


def log_debug(msg: str):
    _logger.debug(msg)


def log_warn(msg: str):
    _logger.warning(msg)


def log_error(msg: str):
    _logger.error(msg)
