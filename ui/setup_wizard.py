"""
首次設定精靈 (Setup Wizard)
引導新使用者完成：
步驟 1: 驅動偵測與安裝 (Interception, ViGEm)
步驟 2: 選擇目標遊戲視窗 (下拉選單或準星吸附)
步驟 3: 設定全域熱鍵 (開始/暫停、停止)
"""
from __future__ import annotations
from typing import Optional

from PyQt6.QtWidgets import (
    QWizard, QWizardPage, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFrame, QProgressBar, QMessageBox, QComboBox
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtGui import QFont

from utils.driver_installer import (
    is_interception_installed, is_vigem_installed,
    install_interception, install_vigem
)
from core.window_manager import WindowManager, WindowInfo
from ui.dialogs.hotkey_dialog import HotkeyCapture


class DriverPage(QWizardPage):
    """步驟 1: 驅動程式檢查與安裝"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTitle("步驟 1 / 3：驅動程式環境檢查")
        self.setSubTitle("GameScript Pro 需要底層驅動程式以實現獨立虛擬通道與後台控制，不干擾您的鍵鼠。")

        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(20, 20, 20, 20)

        # 說明卡片
        info_card = QFrame()
        info_card.setObjectName("card")
        info_card.setStyleSheet("background-color: #1e2430; border-radius: 8px; padding: 14px;")
        ic_layout = QVBoxLayout(info_card)
        ic_layout.setSpacing(8)

        self.lbl_interception = QLabel("🔍 偵測 Interception Driver (虛擬鍵鼠驅動)...")
        self.lbl_interception.setStyleSheet("font-size: 13px; color: #e2e8f0;")
        ic_layout.addWidget(self.lbl_interception)

        self.lbl_vigem = QLabel("🔍 偵測 ViGEm Bus (虛擬搖桿驅動)...")
        self.lbl_vigem.setStyleSheet("font-size: 13px; color: #e2e8f0;")
        ic_layout.addWidget(self.lbl_vigem)

        layout.addWidget(info_card)

        # 安裝按鈕區
        btn_layout = QHBoxLayout()
        self.btn_install_all = QPushButton("⚡ 一鍵安裝推薦驅動")
        self.btn_install_all.setStyleSheet(
            "background-color: #3b82f6; color: white; padding: 8px 16px; border-radius: 6px; font-weight: bold;"
        )
        self.btn_install_all.clicked.connect(self._install_all_drivers)

        self.btn_recheck = QPushButton("🔄 重新偵測")
        self.btn_recheck.setStyleSheet(
            "background-color: #334155; color: white; padding: 8px 16px; border-radius: 6px;"
        )
        self.btn_recheck.clicked.connect(self.check_drivers)

        btn_layout.addWidget(self.btn_install_all)
        btn_layout.addWidget(self.btn_recheck)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        tip_lbl = QLabel(
            "提示：若驅動剛安裝完成，可能需要重啟電腦才能生效。\n"
            "您也可以直接點擊「下一步」以一般模式（PostMessage / SendInput）繼續。"
        )
        tip_lbl.setStyleSheet("color: #94a3b8; font-size: 12px;")
        layout.addWidget(tip_lbl)
        layout.addStretch()

        self.check_drivers()

    def check_drivers(self):
        self.has_interception = is_interception_installed()
        self.has_vigem = is_vigem_installed()

        if self.has_interception:
            self.lbl_interception.setText("✅ Interception Driver: 已安裝並準備就緒")
            self.lbl_interception.setStyleSheet("font-size: 13px; color: #4ade80; font-weight: bold;")
        else:
            self.lbl_interception.setText("⚠️ Interception Driver: 未安裝 (無法使用核心級無干擾後台鍵鼠)")
            self.lbl_interception.setStyleSheet("font-size: 13px; color: #f87171;")

        if self.has_vigem:
            self.lbl_vigem.setText("✅ ViGEm Bus: 已安裝 (支援虛擬 Xbox360 搖桿通道)")
            self.lbl_vigem.setStyleSheet("font-size: 13px; color: #4ade80; font-weight: bold;")
        else:
            self.lbl_vigem.setText("⚠️ ViGEm Bus: 未安裝 (無法模擬虛擬搖桿)")
            self.lbl_vigem.setStyleSheet("font-size: 13px; color: #f87171;")

    def _install_all_drivers(self):
        ok1, msg1 = install_interception()
        ok2, msg2 = install_vigem()
        self.check_drivers()
        QMessageBox.information(
            self,
            "驅動安裝結果",
            f"Interception: {msg1}\nViGEm Bus: {msg2}\n\n若剛完成安裝，請在必要時重新啟動電腦。"
        )


class WindowSelectPage(QWizardPage):
    """步驟 2: 目標遊戲視窗選取"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTitle("步驟 2 / 3：選取目標遊戲視窗")
        self.setSubTitle("請選擇要執行巨集腳本的遊戲或視窗。系統將即時計算相對座標，即使移動視窗也能精準點擊。")

        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(20, 20, 20, 20)

        card = QFrame()
        card.setStyleSheet("background-color: #1e2430; border-radius: 8px; padding: 14px;")
        c_layout = QVBoxLayout(card)

        c_layout.addWidget(QLabel("可見視窗列表："))
        self.combo_windows = QComboBox()
        self.combo_windows.setStyleSheet(
            "background-color: #0f172a; color: #f8fafc; border: 1px solid #334155; padding: 6px; border-radius: 4px;"
        )
        c_layout.addWidget(self.combo_windows)

        btn_refresh = QPushButton("🔄 重新整理視窗列表")
        btn_refresh.setStyleSheet("background-color: #334155; color: white; padding: 6px 12px; border-radius: 4px;")
        btn_refresh.clicked.connect(self._refresh_windows)
        c_layout.addWidget(btn_refresh)

        layout.addWidget(card)

        self.lbl_info = QLabel("尚未選擇視窗（之後亦可在主畫面隨時更換）")
        self.lbl_info.setStyleSheet("color: #38bdf8; font-size: 12px;")
        layout.addWidget(self.lbl_info)
        layout.addStretch()

        self._windows = []
        self._refresh_windows()

    def _refresh_windows(self):
        self.combo_windows.clear()
        self.combo_windows.addItem("【暫不指定，稍後在主視窗選取】", 0)
        self._windows = WindowManager.enumerate_windows()
        for w in self._windows:
            display_text = f"{w.title} ({w.process_name}) [{w.width}x{w.height}]"
            self.combo_windows.addItem(display_text, w.hwnd)

    def get_selected_hwnd(self) -> int:
        return self.combo_windows.currentData() or 0

    def get_selected_title(self) -> str:
        idx = self.combo_windows.currentIndex()
        if idx > 0 and idx - 1 < len(self._windows):
            return self._windows[idx - 1].title
        return ""


class HotkeySetupPage(QWizardPage):
    """步驟 3: 設定全域控制熱鍵"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTitle("步驟 3 / 3：設定全域熱鍵")
        self.setSubTitle("全域熱鍵在遊戲處於前後台時皆可發揮作用。")

        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(20, 20, 20, 20)

        card = QFrame()
        card.setStyleSheet("background-color: #1e2430; border-radius: 8px; padding: 14px;")
        c_layout = QVBoxLayout(card)
        c_layout.setSpacing(12)

        # 開始 / 暫停鍵 (必選)
        row1 = QHBoxLayout()
        lbl1 = QLabel("開始 / 暫停熱鍵 (*必填):")
        lbl1.setStyleSheet("color: #e2e8f0; font-weight: bold;")
        self.capture_toggle = HotkeyCapture("Ctrl+F1")
        row1.addWidget(lbl1)
        row1.addWidget(self.capture_toggle)
        c_layout.addLayout(row1)

        # 停止鍵 (選填)
        row2 = QHBoxLayout()
        lbl2 = QLabel("強制停止熱鍵 (選填):")
        lbl2.setStyleSheet("color: #94a3b8;")
        self.capture_stop = HotkeyCapture("F12")
        row2.addWidget(lbl2)
        row2.addWidget(self.capture_stop)
        c_layout.addLayout(row2)

        layout.addWidget(card)

        tip_lbl = QLabel("點擊按鈕後，按下鍵盤上的任意按鍵或組合鍵（如 Ctrl+F1、Alt+Q）即可完成設定。")
        tip_lbl.setStyleSheet("color: #64748b; font-size: 12px;")
        layout.addWidget(tip_lbl)
        layout.addStretch()

    def get_hotkeys(self) -> dict:
        return {
            "start_pause": self.capture_toggle.get_key(),
            "stop": self.capture_stop.get_key()
        }


class SetupWizard(QWizard):
    """GameScript Pro 首次設定精靈導覽視窗"""

    wizard_finished = pyqtSignal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("GameScript Pro - 首次使用導覽")
        self.resize(650, 480)
        self.setStyleSheet("""
            QWizard {
                background-color: #0f172a;
                color: #f8fafc;
            }
            QLabel {
                color: #f8fafc;
            }
        """)

        self.page_driver = DriverPage(self)
        self.page_window = WindowSelectPage(self)
        self.page_hotkey = HotkeySetupPage(self)

        self.addPage(self.page_driver)
        self.addPage(self.page_window)
        self.addPage(self.page_hotkey)

    def accept(self):
        """完成精靈"""
        result_data = {
            "target_hwnd": self.page_window.get_selected_hwnd(),
            "target_title": self.page_window.get_selected_title(),
            "hotkeys": self.page_hotkey.get_hotkeys(),
        }
        self.wizard_finished.emit(result_data)
        super().accept()
