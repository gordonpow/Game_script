"""
Qt 跨版本與跨綁定相容層 (Qt Compatibility Layer)
支援 PySide6 與 PyQt6 自動橋接
在 Windows / Anaconda 環境下優先使用 PySide6 以徹底消除 PyQt6 的 DLL 衝突問題
"""
from __future__ import annotations
import sys
import logging

logger = logging.getLogger("GameScriptPro.QtCompat")

QT_BINDING = None

# 1. 優先嘗試 PySide6（Anaconda 環境下 100% 穩定相容）
try:
    from PySide6 import QtCore, QtGui, QtWidgets
    from PySide6.QtCore import Qt, Signal, Slot, QTimer, QSize, QPoint, QRect
    
    # 注入 PyQt 慣用名稱
    QtCore.pyqtSignal = Signal
    QtCore.pyqtSlot = Slot

    # 橋接 sys.modules 中的 PyQt6 命名空間
    import types
    pyqt6_mod = types.ModuleType("PyQt6")
    pyqt6_mod.QtCore = QtCore
    pyqt6_mod.QtGui = QtGui
    pyqt6_mod.QtWidgets = QtWidgets

    sys.modules["PyQt6"] = pyqt6_mod
    sys.modules["PyQt6.QtCore"] = QtCore
    sys.modules["PyQt6.QtGui"] = QtGui
    sys.modules["PyQt6.QtWidgets"] = QtWidgets

    QT_BINDING = "PySide6"
    logger.info("已啟用 Qt 官方 PySide6 核心與 PyQt6 相容橋接。")

except Exception as _pyside_err:
    # 2. 若無 PySide6，嘗試原生 PyQt6
    try:
        from PyQt6 import QtCore, QtGui, QtWidgets
        from PyQt6.QtCore import Qt, pyqtSignal, pyqtSlot, QTimer, QSize, QPoint, QRect
        QT_BINDING = "PyQt6"
    except Exception as _pyqt_err:
        raise ImportError(
            f"無法載入 PySide6 亦無法載入 PyQt6。\n"
            f"PySide6 錯誤: {_pyside_err}\n"
            f"PyQt6 錯誤: {_pyqt_err}\n"
            f"請執行 pip install PySide6 以安裝支援的 GUI 核心。"
        )

__all__ = [
    "QtCore",
    "QtGui",
    "QtWidgets",
    "Qt",
    "pyqtSignal",
    "pyqtSlot",
    "QTimer",
    "QSize",
    "QPoint",
    "QRect",
    "QT_BINDING",
]
