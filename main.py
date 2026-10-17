"""
GameScript Pro — 主程式入口 (main.py)
負責初始化 QApplication、套用深色工業風主題、首次引導與啟動主介面
"""
import sys
import os
import logging

import ui.qt_compat
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon

from ui.theme import MAIN_STYLESHEET
from ui.main_window import MainWindow
from ui.setup_wizard import SetupWizard
from storage.file_manager import FileManager
from models.profile import Profile, HotkeyConfig
from models.macro import Macro
from core.window_manager import WindowInfo

# 設定 logging
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("GameScriptPro")


def main():
    # 支援 Windows 高 DPI 螢幕
    if hasattr(Qt.ApplicationAttribute, 'AA_EnableHighDpiScaling'):
        QApplication.setAttribute(Qt.ApplicationAttribute.AA_EnableHighDpiScaling, True)
    if hasattr(Qt.ApplicationAttribute, 'AA_UseHighDpiPixmaps'):
        QApplication.setAttribute(Qt.ApplicationAttribute.AA_UseHighDpiPixmaps, True)

    app = QApplication(sys.argv)
    app.setApplicationName("GameScript Pro")
    app.setStyleSheet(MAIN_STYLESHEET)

    # 檢查是否已有設定檔
    profiles = FileManager.list_profiles()

    if not profiles:
        logger.info("未檢測到既有 Profile，啟動首次設定精靈 (Setup Wizard)...")
        wizard = SetupWizard()

        def on_wizard_finished(data: dict):
            # 依精靈結果建立預設 Profile
            profile = Profile(name="預設遊戲設定檔")
            if data.get("target_hwnd"):
                profile.target_window = WindowInfo(
                    hwnd=data["target_hwnd"],
                    title=data.get("target_title", "目標遊戲"),
                    process_name="",
                    x=0, y=0, width=1920, height=1080
                )
            if data.get("hotkeys"):
                hk_data = data["hotkeys"]
                profile.hotkeys = HotkeyConfig(
                    start_pause=hk_data.get("start_pause", "Ctrl+F1"),
                    stop=hk_data.get("stop", "F12")
                )
            # 建立一個範例初始巨集
            sample_macro = Macro(name="範例巨集 (連招)")
            profile.macros.append(sample_macro)
            FileManager.save_profile(profile)

        wizard.wizard_finished.connect(on_wizard_finished)
        wizard.exec()

    # 啟動主視窗
    main_win = MainWindow()
    main_win.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
