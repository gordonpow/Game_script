"""
即時系統日誌監控面板 (LogPanel)
提供即時彩色日誌顯示、清空、複製與日誌檔案開啟功能
"""
from __future__ import annotations
import os
import subprocess
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QTextEdit, QFrame, QApplication
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QTextCursor

from ui.theme import COLORS
from core.logger import log_emitter, LOG_FILE


class LogPanel(QFrame):
    """即時日誌監控面板"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._is_collapsed = False
        self._setup_ui()
        self._setup_signals()

    def _setup_ui(self):
        self.setStyleSheet(f"""
            LogPanel {{
                background: {COLORS['bg_secondary']};
                border-top: 1px solid {COLORS['border']};
            }}
        """)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 6, 12, 6)
        layout.setSpacing(6)

        # 頂部控制列
        header_row = QHBoxLayout()
        header_row.setContentsMargins(0, 0, 0, 0)
        header_row.setSpacing(8)

        lbl_icon_title = QLabel("📟 系統執行日誌 (Live System Log)")
        lbl_icon_title.setStyleSheet(f"color: {COLORS['accent']}; font-weight: bold; font-size: 12px;")
        header_row.addWidget(lbl_icon_title)

        self._lbl_engine_info = QLabel("輸入引擎: 檢查中...")
        self._lbl_engine_info.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 11px;")
        header_row.addWidget(self._lbl_engine_info)

        header_row.addStretch()

        btn_copy = QPushButton("📋 複製")
        btn_copy.setFixedHeight(22)
        btn_copy.setStyleSheet(f"font-size: 11px; padding: 2px 8px; background: {COLORS['bg_card']}; border: 1px solid {COLORS['border']};")
        btn_copy.clicked.connect(self._copy_all)
        header_row.addWidget(btn_copy)

        btn_clear = QPushButton("🗑 清空")
        btn_clear.setFixedHeight(22)
        btn_clear.setStyleSheet(f"font-size: 11px; padding: 2px 8px; background: {COLORS['bg_card']}; border: 1px solid {COLORS['border']};")
        btn_clear.clicked.connect(self._clear_log)
        header_row.addWidget(btn_clear)

        btn_open = QPushButton("📁 開啟日誌檔")
        btn_open.setFixedHeight(22)
        btn_open.setStyleSheet(f"font-size: 11px; padding: 2px 8px; background: {COLORS['bg_card']}; border: 1px solid {COLORS['border']};")
        btn_open.clicked.connect(self._open_log_file)
        header_row.addWidget(btn_open)

        self._btn_toggle = QPushButton("▼ 收合")
        self._btn_toggle.setFixedHeight(22)
        self._btn_toggle.setStyleSheet(f"font-size: 11px; padding: 2px 8px; background: {COLORS['bg_card']}; border: 1px solid {COLORS['border']};")
        self._btn_toggle.clicked.connect(self._toggle_collapse)
        header_row.addWidget(self._btn_toggle)

        layout.addLayout(header_row)

        # 日誌終端輸出框
        self._log_text = QTextEdit()
        self._log_text.setReadOnly(True)
        self._log_text.setFont(QFont("Consolas", 10))
        self._log_text.setStyleSheet(f"""
            QTextEdit {{
                background-color: #0b0f14;
                color: #e2e8f0;
                border: 1px solid {COLORS['border']};
                border-radius: 4px;
                padding: 6px;
            }}
        """)
        self._log_text.setFixedHeight(120)
        layout.addWidget(self._log_text)

    def _setup_signals(self):
        log_emitter.new_log.connect(self.append_log)

    def set_engine_info(self, info: str):
        self._lbl_engine_info.setText(f"當前通道: {info}")

    def append_log(self, formatted_msg: str, level: str):
        color = "#e2e8f0"
        if level == "DEBUG":
            color = "#94a3b8"
        elif level == "WARNING":
            color = "#fbbf24"
        elif level == "ERROR":
            color = "#f87171"
        elif level == "INFO":
            color = "#38bdf8"

        # 轉義 HTML 標籤
        safe_msg = formatted_msg.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        html_line = f"<span style='color: {color}; font-family: Consolas;'>{safe_msg}</span>"
        self._log_text.append(html_line)

        # 自動滾動到底部
        cursor = self._log_text.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self._log_text.setTextCursor(cursor)

    def _clear_log(self):
        self._log_text.clear()

    def _copy_all(self):
        plain_text = self._log_text.toPlainText()
        clipboard = QApplication.clipboard()
        clipboard.setText(plain_text)

    def _open_log_file(self):
        try:
            if LOG_FILE.exists():
                os.startfile(str(LOG_FILE))
        except Exception:
            pass

    def _toggle_collapse(self):
        self._is_collapsed = not self._is_collapsed
        if self._is_collapsed:
            self._log_text.hide()
            self._btn_toggle.setText("▲ 展開日誌")
        else:
            self._log_text.show()
            self._btn_toggle.setText("▼ 收合")
