"""
驅動程式管理中心對話框 (Driver Dialog)
提供 Interception 與 ViGEmBus 驅動的狀態檢查、一鍵提權安裝與重開機提醒
"""
from __future__ import annotations
import os
from typing import Optional

from ui.qt_compat import (
    QtWidgets, QtCore, QtGui, Qt
)
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFrame, QMessageBox, QGroupBox
)
from PyQt6.QtCore import pyqtSignal
from PyQt6.QtGui import QFont

from utils.driver_installer import (
    is_interception_installed, is_vigem_installed,
    install_interception, install_vigem
)
from core.logger import log_info, log_warn, log_error
from ui.theme import COLORS


class DriverDialog(QDialog):
    """驅動程式管理中心對話框"""

    drivers_updated = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("🛠️ 核心驅動程式管理中心 - GameScript Pro")
        self.setMinimumWidth(560)
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {COLORS['bg_primary']};
                color: {COLORS['text_primary']};
            }}
            QGroupBox {{
                font-weight: bold;
                font-size: 13px;
                border: 1px solid {COLORS['border']};
                border-radius: 8px;
                margin-top: 12px;
                padding-top: 16px;
                background-color: {COLORS['bg_secondary']};
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 6px;
                color: {COLORS['accent']};
            }}
        """)

        self._setup_ui()
        self.refresh_status()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.setContentsMargins(20, 20, 20, 20)

        # 頂部標題說明
        header_lbl = QLabel("系統獨立通道與虛擬硬體驅動管理")
        header_lbl.setStyleSheet("font-size: 16px; font-weight: bold; color: #ffffff;")
        layout.addWidget(header_lbl)

        desc_lbl = QLabel(
            "GameScript Pro 透過底層硬體過濾驅動與虛擬匯流排，達成完全不搶前台焦點、"
            "獨立運作的自動化體驗。"
        )
        desc_lbl.setWordWrap(True)
        desc_lbl.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 12px;")
        layout.addWidget(desc_lbl)

        # ── 1. Interception 核心鍵鼠驅動 ──
        gb_inter = QGroupBox("1. Interception 鍵鼠核心過濾驅動 (Keyboard/Mouse Filter)")
        l_inter = QVBoxLayout(gb_inter)
        l_inter.setSpacing(8)

        self._lbl_inter_status = QLabel("狀態: 檢測中...")
        self._lbl_inter_status.setStyleSheet("font-size: 13px;")
        l_inter.addWidget(self._lbl_inter_status)

        lbl_inter_desc = QLabel(
            "• 功能：在 Windows 核心驅動層直接注入按鍵與滑鼠訊號，繞過遊戲反外掛檢測。\n"
            "• 生效條件：安裝後【必須重新開機一次】Windows 核心方能加載驅動。"
        )
        lbl_inter_desc.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 11px;")
        lbl_inter_desc.setWordWrap(True)
        l_inter.addWidget(lbl_inter_desc)

        h_inter_btns = QHBoxLayout()
        self._btn_install_inter = QPushButton("⚡ 一鍵安裝 Interception 驅動")
        self._btn_install_inter.setStyleSheet("""
            QPushButton {
                background-color: #2563eb; color: white; font-weight: bold;
                padding: 6px 14px; border-radius: 4px;
            }
            QPushButton:hover { background-color: #1d4ed8; }
        """)
        self._btn_install_inter.clicked.connect(self._do_install_interception)
        h_inter_btns.addWidget(self._btn_install_inter)
        h_inter_btns.addStretch()
        l_inter.addLayout(h_inter_btns)

        layout.addWidget(gb_inter)

        # ── 2. ViGEmBus 虛擬手把匯流排驅動 ──
        gb_vigem = QGroupBox("2. ViGEmBus 虛擬搖桿手把驅動 (Virtual Gamepad Bus)")
        l_vigem = QVBoxLayout(gb_vigem)
        l_vigem.setSpacing(8)

        self._lbl_vigem_status = QLabel("狀態: 檢測中...")
        self._lbl_vigem_status.setStyleSheet("font-size: 13px;")
        l_vigem.addWidget(self._lbl_vigem_status)

        lbl_vigem_desc = QLabel(
            "• 功能：在系統層虛擬出標準微軟 Xbox 360 / DS4 實體手把，支援後台掛機且不搶前台鍵鼠。\n"
            "• 生效條件：安裝完成後【立即生效】，無需重新開機。"
        )
        lbl_vigem_desc.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 11px;")
        lbl_vigem_desc.setWordWrap(True)
        l_vigem.addWidget(lbl_vigem_desc)

        h_vigem_btns = QHBoxLayout()
        self._btn_install_vigem = QPushButton("⚡ 一鍵安裝 / 修復 ViGEmBus")
        self._btn_install_vigem.setStyleSheet("""
            QPushButton {
                background-color: #059669; color: white; font-weight: bold;
                padding: 6px 14px; border-radius: 4px;
            }
            QPushButton:hover { background-color: #047857; }
        """)
        self._btn_install_vigem.clicked.connect(self._do_install_vigem)
        h_vigem_btns.addWidget(self._btn_install_vigem)
        h_vigem_btns.addStretch()
        l_vigem.addLayout(h_vigem_btns)

        layout.addWidget(gb_vigem)

        # ── 底部控制按鈕 ──
        b_layout = QHBoxLayout()
        self._btn_install_all = QPushButton("🚀 一鍵自動安裝全部驅動")
        self._btn_install_all.setStyleSheet("""
            QPushButton {
                background-color: #ea580c; color: white; font-weight: bold; font-size: 13px;
                padding: 8px 18px; border-radius: 6px;
            }
            QPushButton:hover { background-color: #c2410c; }
        """)
        self._btn_install_all.clicked.connect(self._do_install_all)

        self._btn_refresh = QPushButton("🔄 重新偵測")
        self._btn_refresh.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['bg_card']}; color: {COLORS['text_primary']};
                border: 1px solid {COLORS['border']}; padding: 8px 16px; border-radius: 6px;
            }}
            QPushButton:hover {{ background-color: #334155; }}
        """)
        self._btn_refresh.clicked.connect(self.refresh_status)

        self._btn_close = QPushButton("關閉")
        self._btn_close.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['bg_card']}; color: {COLORS['text_muted']};
                border: 1px solid {COLORS['border']}; padding: 8px 16px; border-radius: 6px;
            }}
            QPushButton:hover {{ color: white; }}
        """)
        self._btn_close.clicked.connect(self.accept)

        b_layout.addWidget(self._btn_install_all)
        b_layout.addWidget(self._btn_refresh)
        b_layout.addStretch()
        b_layout.addWidget(self._btn_close)
        layout.addLayout(b_layout)

    def refresh_status(self):
        """重新整理兩大驅動的安裝與運作狀態"""
        inter_ok = is_interception_installed()
        vigem_ok = is_vigem_installed()

        if inter_ok:
            self._lbl_inter_status.setText("✅ Interception 驅動：已安裝並加載生效 (核心過濾通道就緒)")
            self._lbl_inter_status.setStyleSheet("font-size: 13px; color: #4ade80; font-weight: bold;")
            self._btn_install_inter.setText("重新安裝 / 修復 Interception")
        else:
            self._lbl_inter_status.setText("⚠️ Interception 驅動：未安裝 或 尚未重開機加載驅動")
            self._lbl_inter_status.setStyleSheet("font-size: 13px; color: #f87171; font-weight: bold;")
            self._btn_install_inter.setText("⚡ 一鍵安裝 Interception (需重開機)")

        if vigem_ok:
            self._lbl_vigem_status.setText("✅ ViGEmBus 驅動：已安裝就緒 (虛擬 Xbox 360 手把正常運作)")
            self._lbl_vigem_status.setStyleSheet("font-size: 13px; color: #4ade80; font-weight: bold;")
            self._btn_install_vigem.setText("重新安裝 / 修復 ViGEmBus")
        else:
            self._lbl_vigem_status.setText("⚠️ ViGEmBus 驅動：未安裝 (手把模式無法模擬硬體訊號)")
            self._lbl_vigem_status.setStyleSheet("font-size: 13px; color: #f87171; font-weight: bold;")
            self._btn_install_vigem.setText("⚡ 一鍵安裝 ViGEmBus (立即生效)")

        self.drivers_updated.emit()

    def _do_install_interception(self):
        """執行安裝 Interception 驅動"""
        log_info("🛠️ [驅動中心] 正在啟動 Interception 核心驅動安裝程序 (請在彈出 UAC 提示時允許)...")
        ok, msg = install_interception()
        self.refresh_status()
        if ok:
            log_info(f"✅ [驅動中心] Interception 安裝完成: {msg}")
            QMessageBox.information(
                self,
                "Interception 驅動安裝完成",
                "Interception 核心過濾驅動已成功註冊！\n\n"
                "⚠️ 重要提示：\n"
                "Windows 核心需要【重新啟動電腦】才能正式加載鍵鼠過濾驅動。\n"
                "若暫時不便重開機，軟體將自動使用相容的純後台 (PostMessage) 通道運作。"
            )
        else:
            log_error(f"❌ [驅動中心] Interception 安裝失敗: {msg}")
            QMessageBox.warning(self, "安裝失敗", f"無法安裝 Interception 驅動:\n{msg}")

    def _do_install_vigem(self):
        """執行安裝 ViGEmBus 驅動"""
        log_info("🛠️ [驅動中心] 正在啟動 ViGEmBus 虛擬手把安裝程序 (請在彈出 UAC 提示時允許)...")
        ok, msg = install_vigem()
        self.refresh_status()
        if ok:
            log_info(f"✅ [驅動中心] ViGEmBus 安裝完成: {msg}")
            QMessageBox.information(
                self,
                "ViGEmBus 驅動安裝完成",
                "ViGEmBus 虛擬手把驅動已安裝成功！\n\n"
                "✅ 虛擬手把已立即生效（無需重新開機）。\n"
                "您現在可以切換至手把模式或在測試網站進行搖桿操作測試！"
            )
        else:
            log_error(f"❌ [驅動中心] ViGEmBus 安裝失敗: {msg}")
            QMessageBox.warning(self, "安裝失敗", f"無法安裝 ViGEmBus 驅動:\n{msg}")

    def _do_install_all(self):
        """一鍵安裝全部驅動"""
        log_info("🚀 [驅動中心] 開始執行一鍵安裝全部驅動程序...")
        ok_v, msg_v = install_vigem()
        ok_i, msg_i = install_interception()
        self.refresh_status()

        result_txt = (
            f"1. ViGEmBus 虛擬手把: {'✅ 成功' if ok_v else '❌ 失敗'} ({msg_v})\n"
            f"2. Interception 核心驅動: {'✅ 成功' if ok_i else '❌ 失敗'} ({msg_i})\n\n"
        )
        if ok_i:
            result_txt += "⚠️ 提醒：Interception 驅動需【重新開機一次】後方能加載核心過濾。\nViGEmBus 手把驅動則已即刻生效！"

        QMessageBox.information(self, "一鍵驅動安裝結果", result_txt)
