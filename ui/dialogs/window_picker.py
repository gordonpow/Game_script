"""
視窗選取對話框
提供下拉選單 + 準星吸附兩種選取方式
"""
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QComboBox, QFrame, QListWidget, QListWidgetItem
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QFont

from core.window_manager import WindowManager, WindowInfo
from ui.theme import COLORS


class RefreshThread(QThread):
    """非同步重新整理視窗清單"""
    finished = pyqtSignal(list)

    def run(self):
        windows = WindowManager.get_all_windows()
        self.finished.emit(windows)


class WindowPickerDialog(QDialog):
    """
    視窗選取對話框
    - 下拉清單（含搜尋過濾）
    - 準星吸附（移動滑鼠到視窗上再點擊選取）
    """
    window_selected = pyqtSignal(int, str)   # hwnd, title

    def __init__(self, current_hwnd: int = 0, parent=None):
        super().__init__(parent)
        self.setWindowTitle("選取目標視窗")
        self.setModal(True)
        self.setMinimumSize(560, 460)
        self._current_hwnd = current_hwnd
        self._windows: list[WindowInfo] = []
        self._selected_hwnd = 0
        self._selected_title = ""
        self._picker_active = False
        self._setup_ui()
        self._refresh_windows()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 16)

        # 標題
        title_row = QHBoxLayout()
        title = QLabel("🎯  選取目標視窗")
        title.setStyleSheet(f"color: {COLORS['accent']}; font-size: 15px; font-weight: bold;")
        title_row.addWidget(title)
        title_row.addStretch()

        refresh_btn = QPushButton("⟳  重新整理")
        refresh_btn.clicked.connect(self._refresh_windows)
        title_row.addWidget(refresh_btn)
        layout.addLayout(title_row)

        hint = QLabel("選取後，所有滑鼠座標將以此視窗為基準進行比例換算")
        hint.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 11px;")
        layout.addWidget(hint)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"background: {COLORS['border']};")
        layout.addWidget(sep)

        # ── 視窗清單 ──────────────────────────────────────────
        layout.addWidget(QLabel("可用視窗清單："))
        self._list = QListWidget()
        self._list.setStyleSheet(f"""
            QListWidget {{
                background: {COLORS['bg_input']};
                border: 1px solid {COLORS['border_bright']};
                border-radius: 4px;
                font-family: Consolas, monospace;
                font-size: 11px;
            }}
            QListWidget::item {{ padding: 6px 8px; }}
            QListWidget::item:hover {{ background: {COLORS['bg_hover']}; }}
            QListWidget::item:selected {{ background: {COLORS['bg_selected']}; color: {COLORS['accent']}; }}
        """)
        self._list.currentItemChanged.connect(self._on_list_selection)
        layout.addWidget(self._list, stretch=1)

        # ── 載入中提示 ────────────────────────────────────────
        self._loading_label = QLabel("載入中...")
        self._loading_label.setStyleSheet(f"color: {COLORS['text_secondary']};")
        self._loading_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._loading_label)
        self._loading_label.hide()

        # ── 準星吸附 ──────────────────────────────────────────
        sep2 = QFrame()
        sep2.setFrameShape(QFrame.Shape.HLine)
        sep2.setStyleSheet(f"background: {COLORS['border']};")
        layout.addWidget(sep2)

        crosshair_row = QHBoxLayout()
        crosshair_label = QLabel("或使用準星吸附：")
        crosshair_label.setStyleSheet(f"color: {COLORS['text_secondary']};")
        crosshair_row.addWidget(crosshair_label)
        crosshair_row.addStretch()

        self._crosshair_btn = QPushButton("✛  準星吸附選取")
        self._crosshair_btn.setStyleSheet(f"""
            QPushButton {{
                background: {COLORS['bg_card']};
                border: 1px solid {COLORS['accent2']};
                color: {COLORS['accent2']};
                border-radius: 4px;
                padding: 6px 14px;
            }}
            QPushButton:hover {{ background: #103040; }}
        """)
        self._crosshair_btn.clicked.connect(self._start_crosshair)
        crosshair_row.addWidget(self._crosshair_btn)
        layout.addLayout(crosshair_row)

        self._crosshair_hint = QLabel("")
        self._crosshair_hint.setStyleSheet(f"color: {COLORS['accent2']}; font-size: 11px;")
        self._crosshair_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._crosshair_hint)

        # ── 選取結果顯示 ──────────────────────────────────────
        self._selected_display = QLabel("尚未選取視窗")
        self._selected_display.setStyleSheet(f"""
            background: {COLORS['bg_card']};
            border: 1px solid {COLORS['border']};
            border-radius: 4px;
            padding: 8px;
            color: {COLORS['text_secondary']};
            font-size: 11px;
        """)
        layout.addWidget(self._selected_display)

        # ── 按鈕 ──────────────────────────────────────────────
        btn_row = QHBoxLayout()
        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(self.reject)
        self._ok_btn = QPushButton("確認選取")
        self._ok_btn.setObjectName("btn_accent")
        self._ok_btn.setEnabled(False)
        self._ok_btn.clicked.connect(self._on_ok)
        btn_row.addStretch()
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(self._ok_btn)
        layout.addLayout(btn_row)

    def _refresh_windows(self):
        self._list.clear()
        self._loading_label.show()
        self._thread = RefreshThread()
        self._thread.finished.connect(self._on_windows_loaded)
        self._thread.start()

    def _on_windows_loaded(self, windows: list):
        self._loading_label.hide()
        self._windows = windows
        self._list.clear()
        for win in windows:
            item = QListWidgetItem(f"[{win.hwnd}]  {win.exe_name}  —  {win.title}")
            item.setData(Qt.ItemDataRole.UserRole, win.hwnd)
            self._list.addItem(item)
            if win.hwnd == self._current_hwnd:
                self._list.setCurrentItem(item)

    def _on_list_selection(self, item, _):
        if not item:
            return
        hwnd = item.data(Qt.ItemDataRole.UserRole)
        win = next((w for w in self._windows if w.hwnd == hwnd), None)
        if win:
            self._set_selection(win.hwnd, win.title)

    def _set_selection(self, hwnd: int, title: str):
        self._selected_hwnd = hwnd
        self._selected_title = title
        self._selected_display.setText(
            f"✅  已選取：{title}\n"
            f"   HWND: {hwnd}"
        )
        self._selected_display.setStyleSheet(f"""
            background: {COLORS['bg_card']};
            border: 1px solid {COLORS['success']};
            border-radius: 4px;
            padding: 8px;
            color: {COLORS['success']};
            font-size: 11px;
        """)
        self._ok_btn.setEnabled(True)

    def _start_crosshair(self):
        """啟動準星吸附模式"""
        self._crosshair_hint.setText("⚡  請將滑鼠移至目標視窗，點擊左鍵選取...")
        self._crosshair_btn.setEnabled(False)
        self.hide()  # 隱藏對話框避免干擾

        def on_picked(hwnd: int):
            self.show()
            self._crosshair_btn.setEnabled(True)
            self._crosshair_hint.setText("")
            import win32gui
            title = win32gui.GetWindowText(hwnd)
            self._set_selection(hwnd, title)
            # 在清單中高亮
            for i in range(self._list.count()):
                item = self._list.item(i)
                if item.data(Qt.ItemDataRole.UserRole) == hwnd:
                    self._list.setCurrentItem(item)
                    break

        # 使用 QTimer 確保 UI 更新後再啟動
        QTimer.singleShot(200, lambda: WindowManager.start_crosshair_picker(on_picked))

    def _on_ok(self):
        if self._selected_hwnd:
            self.window_selected.emit(self._selected_hwnd, self._selected_title)
            self.accept()

    def get_selection(self):
        return self._selected_hwnd, self._selected_title
