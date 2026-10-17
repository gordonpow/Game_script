"""
Profile 管理面板（左側）
"""
from __future__ import annotations
from typing import List, Optional, Callable

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QListWidget, QListWidgetItem,
    QFrame, QInputDialog, QMessageBox, QComboBox
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont

from models.profile import Profile, InputMode, DeviceMode, HotkeyConfig
from storage.file_manager import FileManager
from ui.theme import COLORS


class ProfilePanel(QWidget):
    """左側 Profile 管理面板"""
    profile_selected = pyqtSignal(object)   # 傳 Profile
    profile_changed  = pyqtSignal(object)   # 任何設定改動

    def __init__(self, parent=None):
        super().__init__(parent)
        self._profiles: List[Profile] = []
        self._current: Optional[Profile] = None
        self.setFixedWidth(220)
        self._setup_ui()
        self._load_profiles()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── 頭部 ──────────────────────────────────────────────
        header = QWidget()
        header.setStyleSheet(f"background: {COLORS['bg_secondary']}; border-bottom: 1px solid {COLORS['border']};")
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(10, 10, 10, 10)
        header_layout.setSpacing(6)

        title = QLabel("1️⃣  遊戲設定檔")
        title.setStyleSheet(f"color: {COLORS['accent']}; font-weight: bold; font-size: 13px;")
        header_layout.addWidget(title)

        add_btn = QPushButton("＋  新增遊戲設定檔")
        add_btn.setObjectName("btn_accent")
        add_btn.clicked.connect(self._add_profile)
        header_layout.addWidget(add_btn)

        layout.addWidget(header)

        # ── 清單 ──────────────────────────────────────────────
        self._list = QListWidget()
        self._list.setStyleSheet(f"""
            QListWidget {{
                background: {COLORS['bg_primary']};
                border: none;
            }}
            QListWidget::item {{
                padding: 10px 12px;
                border-bottom: 1px solid {COLORS['border']};
            }}
            QListWidget::item:hover {{ background: {COLORS['bg_hover']}; }}
            QListWidget::item:selected {{
                background: {COLORS['bg_selected']};
                border-left: 3px solid {COLORS['accent']};
                color: {COLORS['accent']};
            }}
        """)
        self._list.currentItemChanged.connect(self._on_selection)
        self._list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._list.customContextMenuRequested.connect(self._show_context_menu)
        layout.addWidget(self._list, stretch=1)

        # ── 遊戲環境配置整合卡片 ─────────────────────────────
        config_box = QFrame()
        config_box.setStyleSheet(f"""
            QFrame {{
                background: {COLORS['bg_secondary']};
                border-top: 1px solid {COLORS['border']};
            }}
        """)
        cb_layout = QVBoxLayout(config_box)
        cb_layout.setContentsMargins(12, 10, 12, 10)
        cb_layout.setSpacing(10)

        # 1. 目標視窗
        win_title_row = QHBoxLayout()
        lbl_wt = QLabel("🎯 目標遊戲視窗")
        lbl_wt.setStyleSheet(f"color: {COLORS['accent']}; font-weight: bold; font-size: 11px;")
        win_title_row.addWidget(lbl_wt)
        cb_layout.addLayout(win_title_row)

        self._win_label = QLabel("尚未綁定視窗")
        self._win_label.setStyleSheet(f"color: {COLORS['text_primary']}; font-size: 11px; background: {COLORS['bg_card']}; padding: 6px; border-radius: 4px; border: 1px solid {COLORS['border']};")
        self._win_label.setWordWrap(True)
        cb_layout.addWidget(self._win_label)

        win_btn_row = QHBoxLayout()
        win_btn_row.setSpacing(6)
        pick_btn = QPushButton("選取視窗")
        pick_btn.setFixedHeight(26)
        pick_btn.clicked.connect(self._pick_window_list)

        crosshair_btn = QPushButton("✛ 準星")
        crosshair_btn.setToolTip("按住拖曳吸附目標視窗")
        crosshair_btn.setFixedHeight(26)
        crosshair_btn.clicked.connect(self._pick_window_crosshair)

        win_btn_row.addWidget(pick_btn, stretch=1)
        win_btn_row.addWidget(crosshair_btn)
        cb_layout.addLayout(win_btn_row)

        # 2. 全域熱鍵
        hk_title_row = QHBoxLayout()
        lbl_hk = QLabel("⌨️ 全域快捷鍵")
        lbl_hk.setStyleSheet(f"color: {COLORS['accent']}; font-weight: bold; font-size: 11px;")
        hk_title_row.addWidget(lbl_hk)
        cb_layout.addLayout(hk_title_row)

        self._hk_label = QLabel("執行: Ctrl+F1 | 錄製: Ctrl+F2")
        self._hk_label.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 11px;")
        cb_layout.addWidget(self._hk_label)

        hk_btn = QPushButton("⚙️ 設定快捷鍵")
        hk_btn.setFixedHeight(26)
        hk_btn.clicked.connect(self._configure_hotkeys)
        cb_layout.addWidget(hk_btn)

        # 3. 輸入模式
        mode_title_row = QHBoxLayout()
        lbl_md = QLabel("🕹️ 虛擬輸入通道")
        lbl_md.setStyleSheet(f"color: {COLORS['accent']}; font-weight: bold; font-size: 11px;")
        mode_title_row.addWidget(lbl_md)
        cb_layout.addLayout(mode_title_row)

        self._input_mode_combo = QComboBox()
        self._input_mode_combo.addItem("純後台獨立通道 (PostMessage - 不搶焦點、前台自由)", InputMode.POST_MESSAGE)
        self._input_mode_combo.addItem("前台相容通道 (SendInput - 100%生效、需焦點)", InputMode.SEND_INPUT)
        self._input_mode_combo.addItem("核心級獨立通道 (Interception - 需重開機生效)", InputMode.INTERCEPTION)
        self._input_mode_combo.currentIndexChanged.connect(self._on_input_mode_changed)
        cb_layout.addWidget(self._input_mode_combo)

        self._device_mode_combo = QComboBox()
        self._device_mode_combo.addItem("模擬鍵盤滑鼠", DeviceMode.KEYBOARD)
        self._device_mode_combo.addItem("模擬虛擬手把 (ViGEm 搖桿 - 後台掛機首選)", DeviceMode.GAMEPAD)
        self._device_mode_combo.addItem("同時支援 (鍵鼠+手把)", DeviceMode.BOTH)
        self._device_mode_combo.currentIndexChanged.connect(self._on_device_mode_changed)
        cb_layout.addWidget(self._device_mode_combo)

        layout.addWidget(config_box)

    def get_current_profile(self) -> Optional[Profile]:
        """取得當前選取的 Profile"""
        return self._current

    # ── Profile 載入 / 儲存 ───────────────────────────────────
    def _load_profiles(self):
        self._profiles = FileManager.load_all_profiles()
        if not self._profiles:
            default_p = Profile(name="預設設定檔")
            FileManager.save_profile(default_p)
            self._profiles = [default_p]
        self._refresh_list()
        if self._profiles:
            self._list.setCurrentRow(0)
            self._current = self._profiles[0]

    def _refresh_list(self):
        self._list.clear()
        for p in self._profiles:
            item = QListWidgetItem(p.name)
            item.setData(Qt.ItemDataRole.UserRole, p.id)
            self._list.addItem(item)

    def _on_selection(self, item, _):
        if not item:
            return
        pid = item.data(Qt.ItemDataRole.UserRole)
        profile = next((p for p in self._profiles if p.id == pid), None)
        if profile:
            self._current = profile
            self._update_info_display()
            self.profile_selected.emit(profile)

    def _update_info_display(self):
        p = self._current
        if not p:
            return
        if p.target_window_title:
            self._win_label.setText(p.target_window_title)
        else:
            self._win_label.setText("尚未選取")

        hk_parts = []
        if getattr(p.hotkeys, "start_pause", ""):
            hk_parts.append(f"執行: {p.hotkeys.start_pause.upper()}")
        if getattr(p.hotkeys, "record_toggle", ""):
            hk_parts.append(f"錄製: {p.hotkeys.record_toggle.upper()}")
        if getattr(p.hotkeys, "stop", ""):
            hk_parts.append(f"停止: {p.hotkeys.stop.upper()}")
        self._hk_label.setText(" | ".join(hk_parts) if hk_parts else "未設定")

        # 同步 Combo
        idx = self._input_mode_combo.findData(p.input_mode)
        if idx >= 0:
            self._input_mode_combo.blockSignals(True)
            self._input_mode_combo.setCurrentIndex(idx)
            self._input_mode_combo.blockSignals(False)

        idx = self._device_mode_combo.findData(p.device_mode)
        if idx >= 0:
            self._device_mode_combo.blockSignals(True)
            self._device_mode_combo.setCurrentIndex(idx)
            self._device_mode_combo.blockSignals(False)

    def _add_profile(self):
        name, ok = QInputDialog.getText(self, "新增設定檔", "設定檔名稱：")
        if ok and name.strip():
            profile = Profile(name=name.strip())
            self._profiles.append(profile)
            FileManager.save_profile(profile)
            self._refresh_list()
            self._list.setCurrentRow(len(self._profiles) - 1)

    def _show_context_menu(self, pos):
        item = self._list.itemAt(pos)
        if not item:
            return
        from PyQt6.QtWidgets import QMenu
        menu = QMenu(self)
        rename_action = menu.addAction("✏  重新命名")
        delete_action = menu.addAction("✕  刪除")
        action = menu.exec(self._list.mapToGlobal(pos))
        if action == rename_action:
            self._rename_profile(item)
        elif action == delete_action:
            self._delete_profile(item)

    def _rename_profile(self, item):
        pid = item.data(Qt.ItemDataRole.UserRole)
        profile = next((p for p in self._profiles if p.id == pid), None)
        if not profile:
            return
        name, ok = QInputDialog.getText(self, "重新命名", "新名稱：", text=profile.name)
        if ok and name.strip():
            profile.name = name.strip()
            FileManager.save_profile(profile)
            self._refresh_list()

    def _delete_profile(self, item):
        pid = item.data(Qt.ItemDataRole.UserRole)
        profile = next((p for p in self._profiles if p.id == pid), None)
        if not profile:
            return
        reply = QMessageBox.question(
            self, "確認刪除", f"確定要刪除「{profile.name}」嗎？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._profiles = [p for p in self._profiles if p.id != pid]
            FileManager.delete_profile(pid)
            self._refresh_list()

    def _pick_window_list(self):
        if not self._current:
            return
        from ui.dialogs.window_picker import WindowPickerDialog
        dlg = WindowPickerDialog(self._current.target_hwnd, self)
        dlg.setStyleSheet(self.styleSheet())
        if dlg.exec():
            hwnd, title = dlg.get_selection()
            self._current.target_hwnd = hwnd
            self._current.target_window_title = title
            self._win_label.setText(title)
            FileManager.save_profile(self._current)
            self.profile_changed.emit(self._current)

    def _pick_window_crosshair(self):
        if not self._current:
            return
        from core.window_manager import WindowManager
        def on_picked(hwnd: int):
            import win32gui
            title = win32gui.GetWindowText(hwnd)
            self._current.target_hwnd = hwnd
            self._current.target_window_title = title
            self._win_label.setText(title)
            FileManager.save_profile(self._current)
            self.profile_changed.emit(self._current)
        WindowManager.start_crosshair_picker(on_picked)

    def _configure_hotkeys(self):
        if not self._current:
            return
        parent_win = self.window()
        hotkey_mgr = getattr(parent_win, "_hotkey_mgr", None)
        if hotkey_mgr:
            hotkey_mgr.disable()
        try:
            from ui.dialogs.hotkey_dialog import HotkeyDialog
            dlg = HotkeyDialog(
                current_start_pause=getattr(self._current.hotkeys, "start_pause", "Ctrl+F1"),
                current_record_toggle=getattr(self._current.hotkeys, "record_toggle", "Ctrl+F2"),
                current_stop=getattr(self._current.hotkeys, "stop", "F12"),
                parent=self
            )
            dlg.setStyleSheet(self.styleSheet())
            if dlg.exec():
                hkeys = dlg.get_hotkeys()
                self._current.hotkeys.start_pause = hkeys.get("start_pause", "Ctrl+F1")
                self._current.hotkeys.record_toggle = hkeys.get("record_toggle", "Ctrl+F2")
                self._current.hotkeys.stop = hkeys.get("stop", "F12")
                self._update_info_display()
                FileManager.save_profile(self._current)
                self.profile_changed.emit(self._current)
        finally:
            if hotkey_mgr:
                hotkey_mgr.enable()

    def _on_input_mode_changed(self):
        if not self._current:
            return
        self._current.input_mode = self._input_mode_combo.currentData()
        FileManager.save_profile(self._current)
        self.profile_changed.emit(self._current)

    def _on_device_mode_changed(self):
        if not self._current:
            return
        self._current.device_mode = self._device_mode_combo.currentData()
        FileManager.save_profile(self._current)
        self.profile_changed.emit(self._current)

    def get_current_profile(self) -> Optional[Profile]:
        return self._current

    def save_current(self):
        if self._current:
            FileManager.save_profile(self._current)
