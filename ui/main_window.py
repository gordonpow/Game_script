"""
主視窗 (MainWindow) - 橫向 AOV 流程與免設定檔自動偵測
- 腳本選擇採用頂部精緻下拉式選單 (QComboBox)
- 取消繁瑣的遊戲設定檔，改為全自動目標視窗記錄與前台追蹤偵測
- 寬敞橫向 AOV 節點時間軸 (結合左側看門狗與節點模組庫)
- 整合頂層核心驅動管理、即時系統日誌與全域熱鍵控制
"""
from __future__ import annotations
import os
import logging
import time
from typing import Optional, List

from ui.qt_compat import (
    QtWidgets, QtCore, QtGui, Qt
)
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QLabel, QPushButton, QStatusBar, QFrame, QMessageBox,
    QComboBox, QInputDialog, QLineEdit
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer, QObject
from PyQt6.QtGui import QFont, QCursor

from models.macro import Macro
from models.node import MacroNode, NodeType
from storage.file_manager import FileManager
from core.window_manager import WindowManager, WindowInfo
from core.input_engine.base import InputEngine
from core.input_engine.postmessage import PostMessageEngine
from core.input_engine.sendinput import SendInputEngine
from core.input_engine.interception import InterceptionEngine
from core.player import Player, PlayerState
from core.recorder import Recorder, RecordFilter
from core.hotkey_manager import HotkeyManager
from utils.driver_installer import is_interception_installed, is_vigem_installed
from ui.theme import COLORS
from ui.panels.editor_panel import EditorPanel
from ui.panels.log_panel import LogPanel
from core.logger import log_info, log_warn, log_error, log_debug

logger = logging.getLogger(__name__)


class ThreadSafeSignalBridge(QObject):
    """跨執行緒信號派發橋接器"""
    toggle_playback = pyqtSignal()
    toggle_recording = pyqtSignal()
    stop_playback = pyqtSignal()
    player_state_changed = pyqtSignal(object)
    player_loop_count = pyqtSignal(int)
    player_error = pyqtSignal(str)
    live_recording_action = pyqtSignal(str, object)
    live_recording_update = pyqtSignal(object)


class WindowSelectComboBox(QComboBox):
    """自訂目標視窗下拉式選單，點擊展開時自動重新整理視窗清單"""
    popup_about_to_show = pyqtSignal()

    def showPopup(self):
        self.popup_about_to_show.emit()
        super().showPopup()


class MainWindow(QMainWindow):
    """GameScript Pro 核心主視窗 (下拉腳本選單 + 下拉式目標視窗選單)"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("GameScript Pro — 通用遊戲獨立虛擬通道腳本工具")
        self.resize(1260, 800)
        self.setMinimumSize(1000, 680)

        # 跨執行緒派發器
        self._bridge = ThreadSafeSignalBridge(self)
        self._bridge.toggle_playback.connect(self._toggle_playback)
        self._bridge.toggle_recording.connect(self._toggle_recording)
        self._bridge.stop_playback.connect(self._stop_playback)
        self._bridge.player_state_changed.connect(self._on_player_state_changed)
        self._bridge.player_loop_count.connect(self._on_player_loop_count)
        self._bridge.player_error.connect(self._on_player_error)
        self._bridge.live_recording_action.connect(self._on_live_recording_action)
        self._bridge.live_recording_update.connect(self._on_live_recording_update)

        # 核心狀態
        self._macros: List[Macro] = []
        self._current_macro: Optional[Macro] = None
        self._engine: Optional[InputEngine] = None
        self._player: Optional[Player] = None
        self._recorder: Optional[Recorder] = None
        self._hotkey_mgr: Optional[HotkeyManager] = None

        self._is_recording = False
        self._target_hwnd: int = 0
        self._target_title: str = ""

        # 讀取歷史視窗紀錄
        win_rec = FileManager.get_window_record()
        self._target_title = win_rec.get("title", "")
        self._target_hwnd = win_rec.get("hwnd", 0)

        self._init_engines()
        self._setup_ui()
        self._setup_signals()
        self._load_macros_and_select()
        self._refresh_target_windows()

        self._setup_hotkeys()
        self._update_status_bar()

        log_info("🌟 [系統] GameScript Pro 初始化就緒 (目標視窗已改為下拉選單模式)")

    def _init_engines(self):
        """初始化輸入引擎與回放引擎"""
        # 預設採用深度後台通道 (PostMessage)
        self._engine = PostMessageEngine()
        self._engine.initialize()

        self._player = Player(engine=self._engine)
        self._player.set_on_state_changed(self._bridge.player_state_changed.emit)
        self._player.set_on_node_executing(self._on_player_node_executing)
        self._player.set_on_loop_count(self._bridge.player_loop_count.emit)
        self._player.set_on_error(self._bridge.player_error.emit)

        self._hotkey_mgr = HotkeyManager()
        self._hotkey_mgr.start()

        # 啟動時自動掛載並激活虛擬手把
        try:
            if is_vigem_installed():
                from core.vigem_engine import get_vigem_engine
                vigem_eng = get_vigem_engine()
                vigem_eng.connect(wake_up=True)
        except Exception as e:
            log_warn(f"⚠️ [手把引擎] 啟動預載虛擬手把失敗: {e}")

    def _setup_ui(self):
        """建構主版面：頂部快捷列 + 中央滿版橫向 AOV 編輯器 + 底部日誌"""
        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)

        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # ── 頂部多功能快捷控制列 (兩行清晰佈局，防止按鈕擠壓) ──
        top_bar = QWidget()
        top_bar.setStyleSheet(f"background: {COLORS['bg_secondary']}; border-bottom: 1px solid {COLORS['border']};")
        top_main_layout = QVBoxLayout(top_bar)
        top_main_layout.setContentsMargins(14, 8, 14, 8)
        top_main_layout.setSpacing(8)

        # ── 第一行：軟體 Logo + 核心驅動 + 主執行操作 ──────────
        row1 = QHBoxLayout()
        row1.setContentsMargins(0, 0, 0, 0)
        row1.setSpacing(12)

        # 1. 軟體 Logo
        logo_title = QLabel("🎮 GameScript Pro")
        logo_title.setStyleSheet(f"color: {COLORS['accent']}; font-weight: bold; font-size: 15px;")
        row1.addWidget(logo_title)

        # 頂層驅動狀態按鈕
        self._btn_driver_manager = QPushButton("🛠️ 核心驅動")
        self._btn_driver_manager.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_driver_manager.setStyleSheet(f"""
            QPushButton {{
                background-color: #1e293b;
                color: #e2e8f0;
                border: 1px solid {COLORS['border']};
                border-radius: 4px;
                padding: 4px 12px;
                font-size: 12px;
            }}
            QPushButton:hover {{
                background-color: #334155;
            }}
        """)
        self._btn_driver_manager.clicked.connect(self._open_driver_dialog)
        row1.addWidget(self._btn_driver_manager)

        row1.addStretch()

        # 快捷控制按鈕 (錄製 / 執行 / 停止)
        self._btn_quick_record = QPushButton("⏺ 錄製 (Ctrl+F2)")
        self._btn_quick_record.setMinimumWidth(125)
        self._btn_quick_record.setStyleSheet("""
            QPushButton {
                padding: 6px 14px;
                font-weight: bold;
                font-size: 12px;
                background: #991b1b;
                color: white;
                border-radius: 4px;
                border: none;
            }
            QPushButton:hover { background: #b91c1c; }
        """)
        self._btn_quick_record.clicked.connect(self._toggle_recording)
        row1.addWidget(self._btn_quick_record)

        self._btn_quick_play = QPushButton("▶ 執行 (Ctrl+F1)")
        self._btn_quick_play.setMinimumWidth(125)
        self._btn_quick_play.setObjectName("btn_accent")
        self._btn_quick_play.setStyleSheet("""
            QPushButton {
                padding: 6px 16px;
                font-weight: bold;
                font-size: 12px;
                background: #ea580c;
                color: white;
                border-radius: 4px;
                border: none;
            }
            QPushButton:hover { background: #f97316; }
        """)
        self._btn_quick_play.clicked.connect(self._toggle_playback)
        row1.addWidget(self._btn_quick_play)

        self._btn_quick_stop = QPushButton("⏹ 停止 (F12)")
        self._btn_quick_stop.setMinimumWidth(100)
        self._btn_quick_stop.setStyleSheet(f"""
            QPushButton {{
                padding: 6px 14px;
                font-size: 12px;
                font-weight: bold;
                background: #334155;
                color: #e2e8f0;
                border: 1px solid {COLORS['border']};
                border-radius: 4px;
            }}
            QPushButton:hover {{ background: #475569; }}
        """)
        self._btn_quick_stop.clicked.connect(self._stop_playback)
        row1.addWidget(self._btn_quick_stop)

        top_main_layout.addLayout(row1)

        # ── 第二行：腳本切換管理 + 目標視窗自動偵測 ─────────────
        row2 = QHBoxLayout()
        row2.setContentsMargins(0, 0, 0, 0)
        row2.setSpacing(10)

        # 📜 巨集腳本下拉式選單與快速管理
        lbl_script = QLabel("📜 腳本：")
        lbl_script.setStyleSheet("font-weight: bold; color: #e2e8f0; font-size: 13px;")
        row2.addWidget(lbl_script)

        self._macro_combo = QComboBox()
        self._macro_combo.setMinimumWidth(180)
        self._macro_combo.setStyleSheet(f"""
            QComboBox {{
                background-color: #1e293b;
                color: #38bdf8;
                border: 1px solid #0284c7;
                border-radius: 4px;
                padding: 4px 10px;
                font-size: 13px;
                font-weight: bold;
                font-family: Consolas, monospace;
            }}
            QComboBox::drop-down {{ border: none; }}
            QComboBox QAbstractItemView {{
                background-color: #1e293b;
                color: #ffffff;
                selection-background-color: #0284c7;
            }}
        """)
        self._macro_combo.currentIndexChanged.connect(self._on_macro_combo_changed)
        row2.addWidget(self._macro_combo)

        # ＋ 新增腳本按鈕
        btn_add_script = QPushButton("＋")
        btn_add_script.setToolTip("新增巨集腳本")
        btn_add_script.setFixedSize(28, 28)
        btn_add_script.setStyleSheet("""
            QPushButton {
                background: #0284c7; color: white; font-weight: bold; font-size: 14px;
                border-radius: 4px; border: none;
            }
            QPushButton:hover { background: #0369a1; }
        """)
        btn_add_script.clicked.connect(self._add_new_macro)
        row2.addWidget(btn_add_script)

        # ✏ 重新命名按鈕
        btn_ren_script = QPushButton("✏")
        btn_ren_script.setToolTip("重新命名當前腳本")
        btn_ren_script.setFixedSize(28, 28)
        btn_ren_script.setStyleSheet("""
            QPushButton {
                background: #334155; color: #e2e8f0; font-size: 13px;
                border-radius: 4px; border: none;
            }
            QPushButton:hover { background: #475569; }
        """)
        btn_ren_script.clicked.connect(self._rename_current_macro)
        row2.addWidget(btn_ren_script)

        # 🗑️ 刪除腳本按鈕
        btn_del_script = QPushButton("🗑️")
        btn_del_script.setToolTip("刪除當前腳本")
        btn_del_script.setFixedSize(28, 28)
        btn_del_script.setStyleSheet("""
            QPushButton {
                background: #334155; color: #f87171; font-size: 13px;
                border-radius: 4px; border: none;
            }
            QPushButton:hover { background: #7f1d1d; color: white; }
        """)
        btn_del_script.clicked.connect(self._delete_current_macro)
        row2.addWidget(btn_del_script)

        # 🎯 目標視窗專屬下拉式選單列
        lbl_target_p = QLabel("🎯 目標視窗：")
        lbl_target_p.setStyleSheet("color: #38bdf8; font-weight: bold; font-size: 12px;")
        row2.addWidget(lbl_target_p)

        self._target_combo = WindowSelectComboBox()
        self._target_combo.setMinimumWidth(260)
        self._target_combo.setMaximumWidth(360)
        self._target_combo.setStyleSheet("""
            QComboBox {
                background: #1e293b;
                color: #fde047;
                font-size: 12px;
                font-weight: bold;
                border: 1px solid #3b82f6;
                border-radius: 4px;
                padding: 4px 8px;
            }
            QComboBox::drop-down {
                border: none;
                width: 20px;
            }
            QComboBox QAbstractItemView {
                background: #1e293b;
                color: #f8fafc;
                selection-background-color: #2563eb;
                selection-color: #ffffff;
                border: 1px solid #3b82f6;
            }
        """)
        self._target_combo.setToolTip("請選擇要注入操作的目標遊戲或視窗（僅此下拉式選單控制）")
        self._target_combo.popup_about_to_show.connect(self._refresh_target_windows)
        self._target_combo.currentIndexChanged.connect(self._on_target_window_changed)
        row2.addWidget(self._target_combo)

        btn_refresh_target = QPushButton("🔄")
        btn_refresh_target.setFixedSize(28, 28)
        btn_refresh_target.setToolTip("重新整理目前系統所有開啟的視窗")
        btn_refresh_target.setStyleSheet("""
            QPushButton {
                background: #334155; color: #38bdf8; font-size: 13px;
                border: 1px solid #475569; border-radius: 4px;
            }
            QPushButton:hover { background: #1e293b; border-color: #38bdf8; }
        """)
        btn_refresh_target.clicked.connect(self._refresh_target_windows)
        row2.addWidget(btn_refresh_target)

        top_main_layout.addLayout(row2)

        main_layout.addWidget(top_bar)

        # ── 中央區域：橫向 AOV 動作序列編輯器 (滿版寬敞) ─────────
        self.editor_panel = EditorPanel(self)
        main_layout.addWidget(self.editor_panel, stretch=1)

        # ── 底部即時日誌監控面板 ──────────────────────────────
        self.log_panel = LogPanel(self)
        self.log_panel.set_engine_info(self._engine.name if self._engine else "未初始化")
        main_layout.addWidget(self.log_panel)

        # ── 底層狀態列 ────────────────────────────────────────
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.setStyleSheet(f"""
            QStatusBar {{
                background: {COLORS['bg_secondary']};
                color: {COLORS['text_secondary']};
                border-top: 1px solid {COLORS['border']};
                padding: 4px 12px;
            }}
        """)

        self.lbl_status_state = QLabel("🟢 待機中")
        self.lbl_status_target = QLabel("目標: 自動鎖定中")
        self.lbl_status_driver = QLabel("驅動狀態: 檢查中")
        self.lbl_status_loop = QLabel("循環: 0")

        self.status_bar.addWidget(self.lbl_status_state)
        self.status_bar.addPermanentWidget(self.lbl_status_loop)
        self.status_bar.addPermanentWidget(self.lbl_status_target)
        self.status_bar.addPermanentWidget(self.lbl_status_driver)

    def _setup_signals(self):
        """連接介面信號"""
        self.editor_panel.macro_changed.connect(self._on_macro_content_changed)
        self.editor_panel.set_record_callback(self._toggle_recording)

    # ── 巨集腳本下拉式選單管理 ────────────────────────────────
    def _load_macros_and_select(self):
        """載入所有腳本至頂部下拉選單"""
        self._macros = FileManager.load_all_macros()
        self._macro_combo.blockSignals(True)
        self._macro_combo.clear()

        for m in self._macros:
            self._macro_combo.addItem(f"📜 {m.name}", m.id)

        self._macro_combo.blockSignals(False)

        if self._macros:
            self._macro_combo.setCurrentIndex(0)
            self._on_macro_combo_changed(0)

    def _on_macro_combo_changed(self, index: int):
        if 0 <= index < len(self._macros):
            self._current_macro = self._macros[index]
            self.editor_panel.set_macro(self._current_macro)
            log_debug(f"📝 [腳本] 切換至腳本「{self._current_macro.name}」(包含 {len(self._current_macro.nodes)} 個動作)")

    def _on_macro_content_changed(self):
        """當動作在畫布中被增刪改時，自動儲存"""
        if self._current_macro:
            FileManager.save_macro(self._current_macro)

    def _add_new_macro(self):
        name, ok = QInputDialog.getText(self, "新增巨集腳本", "請輸入新腳本名稱：", text="新腳本")
        if ok and name.strip():
            new_m = Macro(name=name.strip())
            FileManager.save_macro(new_m)
            self._macros.append(new_m)

            self._macro_combo.blockSignals(True)
            self._macro_combo.addItem(f"📜 {new_m.name}", new_m.id)
            self._macro_combo.setCurrentIndex(len(self._macros) - 1)
            self._macro_combo.blockSignals(False)

            self._on_macro_combo_changed(len(self._macros) - 1)
            log_info(f"✨ [腳本] 已建立並切換至新腳本「{new_m.name}」")

    def _rename_current_macro(self):
        if not self._current_macro:
            return
        name, ok = QInputDialog.getText(self, "重新命名腳本", "請輸入新名稱：", text=self._current_macro.name)
        if ok and name.strip():
            self._current_macro.name = name.strip()
            FileManager.save_macro(self._current_macro)
            cur_idx = self._macro_combo.currentIndex()
            self._macro_combo.setItemText(cur_idx, f"📜 {self._current_macro.name}")
            log_info(f"✏ [腳本] 腳本已重新命名為「{self._current_macro.name}」")

    def _delete_current_macro(self):
        if not self._current_macro:
            return
        if len(self._macros) <= 1:
            QMessageBox.warning(self, "無法刪除", "至少需要保留一個巨集腳本！")
            return

        reply = QMessageBox.question(
            self, "確認刪除",
            f"確定要永久刪除腳本「{self._current_macro.name}」嗎？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            del_id = self._current_macro.id
            FileManager.delete_macro(del_id)
            self._load_macros_and_select()
            log_info(f"🗑️ [腳本] 已刪除腳本 (ID: {del_id})")

    # ── 下拉式目標視窗管理 ────────────────────────────────────
    def _refresh_target_windows(self):
        """刷新系統頂層視窗至下拉選單"""
        curr_hwnd = self._target_hwnd
        self._target_combo.blockSignals(True)
        self._target_combo.clear()

        # 1. 第一項：全螢幕 / 全域
        self._target_combo.addItem("🌐 全螢幕 / 桌面 (全域模擬, HWND: 0)", 0)

        # 2. 列舉所有可見頂層視窗
        wins = WindowManager.get_all_windows()
        my_pid = os.getpid()

        matched_index = 0
        for w in wins:
            if w.pid == my_pid:
                continue
            title = w.title.strip()
            if len(title) < 2:
                continue
            if "gamescript" in title.lower():
                continue

            display_title = title if len(title) <= 26 else title[:25] + "…"
            exe_lower = getattr(w, "exe_name", "").lower()
            icon_tag = "🎮" if any(k in exe_lower for k in ["game", "steam", "genshin", "starrail", "unity", "unreal"]) else "🪟"
            item_text = f"{icon_tag} {display_title} ({w.hwnd})"

            self._target_combo.addItem(item_text, w.hwnd)
            if curr_hwnd and w.hwnd == curr_hwnd:
                matched_index = self._target_combo.count() - 1

        self._target_combo.setCurrentIndex(matched_index)
        self._target_combo.blockSignals(False)

    def _on_target_window_changed(self, index: int):
        """使用者從下拉選單切換目標視窗"""
        if index < 0:
            return
        hwnd = self._target_combo.currentData()
        if hwnd is None:
            hwnd = 0

        self._target_hwnd = hwnd
        raw_text = self._target_combo.currentText()

        if hwnd == 0:
            self._target_title = "全螢幕 / 桌面"
        else:
            win = WindowManager.get_window_by_hwnd(hwnd)
            self._target_title = win.title if win else raw_text

        # 儲存與同步引擎
        FileManager.save_window_record(self._target_title, hwnd)
        if self._engine:
            self._engine.set_target_hwnd(hwnd)
        if self._player:
            self._player.set_target_hwnd(hwnd)

        short_t = self._target_title[:16] + "…" if len(self._target_title) > 16 else self._target_title
        self.lbl_status_target.setText(f"目標: {short_t} ({hwnd})")
        log_info(f"🎯 [目標視窗] 下拉選取鎖定: {self._target_title} (HWND: {hwnd})")

    # ── 驅動對話框 ────────────────────────────────────────────
    def _open_driver_dialog(self):
        from ui.dialogs.driver_dialog import DriverDialog
        dlg = DriverDialog(self)
        dlg.drivers_updated.connect(self._update_status_bar)
        dlg.exec()
        self._update_status_bar()

    def _update_status_bar(self):
        """更新底層狀態列與頂層驅動按鈕"""
        inter_ok = is_interception_installed()
        vigem_ok = is_vigem_installed()
        driver_str = f"Interception: {'✅' if inter_ok else '❌'} | ViGEm: {'✅' if vigem_ok else '❌'}"
        self.lbl_status_driver.setText(driver_str)

        if hasattr(self, "_btn_driver_manager"):
            if inter_ok and vigem_ok:
                self._btn_driver_manager.setText("🛡️ 核心驅動 [就緒]")
                self._btn_driver_manager.setStyleSheet(
                    "background: #064e3b; color: #a7f3d0; border: 1px solid #059669; "
                    "font-weight: bold; font-size: 12px; padding: 5px 12px; border-radius: 4px;"
                )
            elif vigem_ok and not inter_ok:
                self._btn_driver_manager.setText("⚡ 一鍵安裝 Interception 鍵鼠驅動 ⚠️")
                self._btn_driver_manager.setStyleSheet(
                    "background: #b45309; color: #ffffff; border: 1px solid #f59e0b; "
                    "font-weight: bold; font-size: 12px; padding: 5px 12px; border-radius: 4px;"
                )
            else:
                self._btn_driver_manager.setText("⚡ 一鍵安裝底層驅動 ⚠️")
                self._btn_driver_manager.setStyleSheet(
                    "background: #dc2626; color: #ffffff; border: 1px solid #f87171; "
                    "font-weight: bold; font-size: 12px; padding: 5px 12px; border-radius: 4px;"
                )

        short_t = self._target_title[:18] if self._target_title else "自動偵測中"
        self.lbl_status_target.setText(f"目標: {short_t} (HWND: {self._target_hwnd})")

    # ── 全域熱鍵管理 ──────────────────────────────────────────
    def _setup_hotkeys(self):
        if not self._hotkey_mgr:
            return
        self._hotkey_mgr.unregister_all()
        self._hotkey_mgr.register("Ctrl+F2", self._bridge.toggle_recording.emit)
        self._hotkey_mgr.register("Ctrl+F1", self._bridge.toggle_playback.emit)
        self._hotkey_mgr.register("F12", self._bridge.stop_playback.emit)

    # ── 回放控制 ──────────────────────────────────────────────
    def _toggle_playback(self):
        if not self._player:
            return
        state = self._player.state
        if state == PlayerState.IDLE:
            self._start_playback()
        elif state == PlayerState.RUNNING:
            self._player.pause()
        elif state == PlayerState.PAUSED:
            self._player.resume()

    def _start_playback(self):
        if not self._current_macro or not self._current_macro.nodes:
            QMessageBox.warning(self, "無法執行", "當前腳本尚無任何動作節點，請先新增節點或錄製操作！")
            return

        # 即時驗證與更新目標 HWND
        if self._target_hwnd and not WindowManager.is_window_valid(self._target_hwnd):
            if self._target_title:
                re_win = WindowManager.find_window_by_title(self._target_title)
                if re_win:
                    self._target_hwnd = re_win.hwnd
                    log_info(f"🔄 [目標視窗] 重新連線最新目標視窗 HWND: {re_win.hwnd}")

        if self._engine:
            self._engine.set_target_hwnd(self._target_hwnd)
        self._player.set_target_hwnd(self._target_hwnd)

        self._player.start(
            macro=self._current_macro,
            mode=self._current_macro.playback_mode,
            loop_count=self._current_macro.loop_count,
            random_delay=self._current_macro.random_delay,
            min_delay=self._current_macro.min_delay_ms,
            max_delay=self._current_macro.max_delay_ms,
        )

    def _stop_playback(self):
        if self._player:
            self._player.stop()

    def _on_player_state_changed(self, state: PlayerState):
        if state == PlayerState.RUNNING:
            self.lbl_status_state.setText("🚀 回放中...")
            self.lbl_status_state.setStyleSheet(f"color: {COLORS['accent']}; font-weight: bold;")
            self._btn_quick_play.setText("⏸ 暫停 (Ctrl+F1)")
        elif state == PlayerState.PAUSED:
            self.lbl_status_state.setText("⏸ 已暫停")
            self.lbl_status_state.setStyleSheet("color: #fbbf24; font-weight: bold;")
            self._btn_quick_play.setText("▶ 繼續 (Ctrl+F1)")
        else:
            self.lbl_status_state.setText("🟢 待機中")
            self.lbl_status_state.setStyleSheet(f"color: {COLORS['text_primary']};")
            self._btn_quick_play.setText("▶ 執行 (Ctrl+F1)")
            if hasattr(self, "editor_panel"):
                self.editor_panel.highlight_executing_node(-1)

    def _on_player_node_executing(self, index: int, node):
        if hasattr(self, "editor_panel"):
            self.editor_panel.highlight_executing_node(index)

    def _on_player_loop_count(self, count: int):
        self.lbl_status_loop.setText(f"循環: {count}")

    def _on_player_error(self, err_msg: str):
        logger.error(f"回放發生錯誤: {err_msg}")

    # ── 錄製控制 ──────────────────────────────────────────────
    def _toggle_recording(self):
        if not self._is_recording:
            self._start_recording()
        else:
            self._stop_recording()

    def _start_recording(self):
        if not self._current_macro:
            QMessageBox.warning(self, "無法錄製", "請先建立或選取一個巨集腳本！")
            return

        self._recorder = Recorder(
            filter_config=RecordFilter(record_mouse_move=False, min_move_interval_ms=50),
            hwnd=self._target_hwnd
        )
        self._recorder.set_live_callback(self._bridge.live_recording_action.emit)
        self._recorder.set_node_updated_callback(self._bridge.live_recording_update.emit)

        # 屏蔽熱鍵本身
        self._recorder.set_ignore_keys(["ctrl", "ctrl_l", "ctrl_r", "f2", "f1", "f12"])

        self._recorder.start()
        self._is_recording = True

        self.editor_panel.set_live_recording_state(True, "Ctrl+F2")
        self._btn_quick_record.setText("⏹ 停止 (Ctrl+F2)")
        self._btn_quick_record.setStyleSheet("padding: 6px 14px; font-weight: bold; font-size: 13px; background: #dc2626; color: white; border-radius: 4px;")

        self.lbl_status_state.setText("🔴 錄製中...")
        self.lbl_status_state.setStyleSheet("color: #ef4444; font-weight: bold;")
        log_info("⏺ [錄製] 開始錄製操作 (目標: 自動鎖定視窗)")

    def _on_live_recording_action(self, action_name: str, node: MacroNode):
        """即時捕捉動作：更新狀態提示並將新節點即時在畫布上生成"""
        if hasattr(self, "editor_panel"):
            self.editor_panel.update_live_action(action_name)
            if node and self._current_macro:
                self.editor_panel.add_node_live(node)

    def _on_live_recording_update(self, node: MacroNode):
        """即時更新節點屬性 (如按鍵放開時即時刷新按住時長)"""
        if hasattr(self, "editor_panel"):
            self.editor_panel.update_node_live(node)

    def _stop_recording(self):
        if not self._recorder:
            return

        self._recorder.stop()
        self._is_recording = False

        self.editor_panel.set_live_recording_state(False)
        self._btn_quick_record.setText("⏺ 錄製 (Ctrl+F2)")
        self._btn_quick_record.setStyleSheet("padding: 6px 14px; font-weight: bold; font-size: 13px; background: #991b1b; color: white; border-radius: 4px;")

        self.lbl_status_state.setText("🟢 待機中")
        self.lbl_status_state.setStyleSheet(f"color: {COLORS['text_primary']};")

        if self._current_macro:
            FileManager.save_macro(self._current_macro)
            node_cnt = len(self._current_macro.nodes)
            log_info(f"✨ [錄製完成] 成功錄製並生成 {node_cnt} 個動作節點 (即時渲染與排版完成)")
            QMessageBox.information(self, "錄製完成", f"已成功錄製並排版 {node_cnt} 個動作節點！")

    def closeEvent(self, event):
        """關閉視窗清理資源"""
        if hasattr(self, "_window_detector_timer"):
            self._window_detector_timer.stop()
        if self._player:
            self._player.stop()
        if self._hotkey_mgr:
            self._hotkey_mgr.stop()
        if self._engine:
            self._engine.close()
        try:
            from core.vigem_engine import get_vigem_engine
            get_vigem_engine().disconnect()
        except Exception:
            pass
        event.accept()
