"""
巨集清單面板（中側）
顯示當前 Profile 的所有巨集，含回放設定
"""
from __future__ import annotations
from typing import List, Optional

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QListWidget, QListWidgetItem,
    QFrame, QInputDialog, QMessageBox, QComboBox,
    QSpinBox, QCheckBox, QGroupBox
)
from PyQt6.QtCore import Qt, pyqtSignal

from models.macro import Macro, PlaybackMode
from models.profile import Profile
from storage.file_manager import FileManager
from ui.theme import COLORS


class MacroListPanel(QWidget):
    """中側：巨集清單面板"""
    macro_selected = pyqtSignal(object)   # 傳 Macro
    playback_requested = pyqtSignal(object)  # 傳 Macro

    def __init__(self, parent=None):
        super().__init__(parent)
        self._profile: Optional[Profile] = None
        self._current_macro: Optional[Macro] = None
        self.setFixedWidth(240)
        self._setup_ui()

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

        title = QLabel("2️⃣  巨集腳本清單")
        title.setStyleSheet(f"color: {COLORS['accent']}; font-weight: bold; font-size: 13px;")
        header_layout.addWidget(title)

        add_btn = QPushButton("＋  新增巨集腳本")
        add_btn.setObjectName("btn_accent")
        add_btn.clicked.connect(self._add_macro)
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
                font-size: 12px;
            }}
            QListWidget::item:hover {{ background: {COLORS['bg_hover']}; }}
            QListWidget::item:selected {{
                background: {COLORS['bg_selected']};
                border-left: 3px solid {COLORS['accent2']};
                color: {COLORS['accent2']};
            }}
        """)
        self._list.currentItemChanged.connect(self._on_selection)
        self._list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._list.customContextMenuRequested.connect(self._show_context_menu)
        layout.addWidget(self._list, stretch=1)

        # ── 回放設定區塊 ──────────────────────────────────────
        pb_frame = QFrame()
        pb_frame.setStyleSheet(f"background: {COLORS['bg_secondary']}; border-top: 1px solid {COLORS['border']};")
        pb_layout = QVBoxLayout(pb_frame)
        pb_layout.setContentsMargins(10, 10, 10, 10)
        pb_layout.setSpacing(8)

        pb_title = QLabel("▶  回放設定")
        pb_title.setObjectName("label_section")
        pb_layout.addWidget(pb_title)

        # 模式選擇
        mode_row = QHBoxLayout()
        mode_row.addWidget(QLabel("模式："))
        self._mode_combo = QComboBox()
        self._mode_combo.addItem("單次", PlaybackMode.ONCE)
        self._mode_combo.addItem("循環", PlaybackMode.LOOP)
        self._mode_combo.addItem("指定次數", PlaybackMode.REPEAT)
        self._mode_combo.currentIndexChanged.connect(self._on_playback_changed)
        mode_row.addWidget(self._mode_combo)
        pb_layout.addLayout(mode_row)

        # 次數（僅 REPEAT 模式顯示）
        self._count_row_widget = QWidget()
        count_row = QHBoxLayout(self._count_row_widget)
        count_row.setContentsMargins(0, 0, 0, 0)
        count_row.addWidget(QLabel("次數："))
        self._repeat_spin = QSpinBox()
        self._repeat_spin.setRange(1, 99999)
        self._repeat_spin.valueChanged.connect(self._on_playback_changed)
        count_row.addWidget(self._repeat_spin)
        pb_layout.addWidget(self._count_row_widget)

        # 隨機延遲
        self._random_delay_check = QCheckBox("隨機延遲（模擬真人）")
        self._random_delay_check.stateChanged.connect(self._on_playback_changed)
        pb_layout.addWidget(self._random_delay_check)

        self._delay_row_widget = QWidget()
        delay_row = QHBoxLayout(self._delay_row_widget)
        delay_row.setContentsMargins(0, 0, 0, 0)
        delay_row.addWidget(QLabel("延遲範圍："))
        self._delay_min = QSpinBox()
        self._delay_min.setRange(0, 9999)
        self._delay_min.setSuffix("~")
        self._delay_min.valueChanged.connect(self._on_playback_changed)
        self._delay_max = QSpinBox()
        self._delay_max.setRange(0, 9999)
        self._delay_max.setSuffix(" ms")
        self._delay_max.valueChanged.connect(self._on_playback_changed)
        delay_row.addWidget(self._delay_min)
        delay_row.addWidget(self._delay_max)
        pb_layout.addWidget(self._delay_row_widget)

        layout.addWidget(pb_frame)

        # ── 執行按鈕 ──────────────────────────────────────────
        run_frame = QFrame()
        run_frame.setStyleSheet(f"background: {COLORS['bg_secondary']}; border-top: 1px solid {COLORS['border']};")
        run_layout = QVBoxLayout(run_frame)
        run_layout.setContentsMargins(10, 8, 10, 8)

        self._run_btn = QPushButton("▶  執行此巨集")
        self._run_btn.setObjectName("btn_accent")
        self._run_btn.setMinimumHeight(36)
        self._run_btn.clicked.connect(self._on_run)
        self._run_btn.setEnabled(False)
        run_layout.addWidget(self._run_btn)

        layout.addWidget(run_frame)

        self._update_playback_ui()

    # ── 公開介面 ──────────────────────────────────────────────
    def set_profile(self, profile: Optional[Profile]):
        self._profile = profile
        self._current_macro = None
        self._refresh_list()
        if profile and profile.macros:
            self._list.setCurrentRow(0)

    def load_profile(self, profile: Optional[Profile]):
        """相容主視窗的呼叫介面"""
        self.set_profile(profile)

    def get_current_macro(self) -> Optional[Macro]:
        return self._current_macro

    def save_current(self):
        if self._profile:
            FileManager.save_profile(self._profile)

    # ── 清單管理 ──────────────────────────────────────────────
    def _refresh_list(self):
        self._list.clear()
        if not self._profile:
            return
        for macro in self._profile.macros:
            enabled = "✅" if macro.enabled else "⬜"
            item = QListWidgetItem(f"{enabled}  {macro.name}")
            item.setData(Qt.ItemDataRole.UserRole, macro.id)
            self._list.addItem(item)

    def _on_selection(self, item, _):
        if not item or not self._profile:
            return
        mid = item.data(Qt.ItemDataRole.UserRole)
        macro = next((m for m in self._profile.macros if m.id == mid), None)
        if macro:
            self._current_macro = macro
            self._sync_playback_ui(macro)
            self._run_btn.setEnabled(True)
            self.macro_selected.emit(macro)

    def _add_macro(self):
        if not self._profile:
            parent_win = self.window()
            if hasattr(parent_win, "_current_profile") and parent_win._current_profile:
                self.set_profile(parent_win._current_profile)
            else:
                QMessageBox.warning(self, "提示", "請先在左側選取或建立一個設定檔 (Profile)！")
                return

        name, ok = QInputDialog.getText(self, "新增巨集", "巨集名稱：")
        if ok and name.strip():
            macro = Macro(name=name.strip())
            self._profile.macros.append(macro)
            FileManager.save_profile(self._profile)
            self._refresh_list()
            new_idx = len(self._profile.macros) - 1
            self._list.setCurrentRow(new_idx)
            self._current_macro = macro
            self._sync_playback_ui(macro)
            self._run_btn.setEnabled(True)
            self.macro_selected.emit(macro)

    def _show_context_menu(self, pos):
        item = self._list.itemAt(pos)
        if not item:
            return
        from PyQt6.QtWidgets import QMenu
        menu = QMenu(self)
        rename_action = menu.addAction("✏  重新命名")
        toggle_action = menu.addAction("切換啟用/停用")
        duplicate_action = menu.addAction("⧉  複製")
        menu.addSeparator()
        delete_action = menu.addAction("✕  刪除")
        action = menu.exec(self._list.mapToGlobal(pos))

        mid = item.data(Qt.ItemDataRole.UserRole)
        macro = next((m for m in self._profile.macros if m.id == mid), None)
        if not macro:
            return

        if action == rename_action:
            name, ok = QInputDialog.getText(self, "重新命名", "新名稱：", text=macro.name)
            if ok and name.strip():
                macro.name = name.strip()
        elif action == toggle_action:
            macro.enabled = not macro.enabled
        elif action == duplicate_action:
            import uuid
            from copy import deepcopy
            new_macro = deepcopy(macro)
            new_macro.id = str(uuid.uuid4())
            new_macro.name = f"{macro.name} (複製)"
            self._profile.macros.append(new_macro)
        elif action == delete_action:
            reply = QMessageBox.question(
                self, "確認刪除", f"確定刪除「{macro.name}」？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes:
                self._profile.macros = [m for m in self._profile.macros if m.id != mid]
                self._current_macro = None

        FileManager.save_profile(self._profile)
        self._refresh_list()

    # ── 回放設定 UI ───────────────────────────────────────────
    def _sync_playback_ui(self, macro: Macro):
        """將 macro.playback 同步到 UI 控制項"""
        pb = macro.playback
        # 阻止信號觸發儲存
        self._mode_combo.blockSignals(True)
        self._repeat_spin.blockSignals(True)
        self._random_delay_check.blockSignals(True)
        self._delay_min.blockSignals(True)
        self._delay_max.blockSignals(True)

        idx = self._mode_combo.findData(pb.mode)
        if idx >= 0:
            self._mode_combo.setCurrentIndex(idx)
        self._repeat_spin.setValue(pb.repeat_count)
        self._random_delay_check.setChecked(pb.random_delay)
        self._delay_min.setValue(pb.random_delay_min_ms)
        self._delay_max.setValue(pb.random_delay_max_ms)

        self._mode_combo.blockSignals(False)
        self._repeat_spin.blockSignals(False)
        self._random_delay_check.blockSignals(False)
        self._delay_min.blockSignals(False)
        self._delay_max.blockSignals(False)

        self._update_playback_ui()

    def _on_playback_changed(self):
        """回放設定改動 → 儲存到 macro.playback"""
        if not self._current_macro:
            return
        pb = self._current_macro.playback
        pb.mode = self._mode_combo.currentData()
        pb.repeat_count = self._repeat_spin.value()
        pb.random_delay = self._random_delay_check.isChecked()
        pb.random_delay_min_ms = self._delay_min.value()
        pb.random_delay_max_ms = max(self._delay_max.value(), self._delay_min.value())
        self._update_playback_ui()
        if self._profile:
            FileManager.save_profile(self._profile)

    def _update_playback_ui(self):
        mode = self._mode_combo.currentData()
        show_count = (mode == PlaybackMode.REPEAT)
        self._count_row_widget.setVisible(show_count)
        show_delay = self._random_delay_check.isChecked()
        self._delay_row_widget.setVisible(show_delay)

    def _on_run(self):
        if self._current_macro:
            self.playback_requested.emit(self._current_macro)
