"""
熱鍵設定對話框
使用底層監聽確保在任何輸入法與焦點狀態下皆能 100% 準確捕獲組合鍵
包含：開始/暫停執行、開始/停止錄製、強制停止執行 三大熱鍵
"""
from __future__ import annotations
import threading
from typing import Optional, Set

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFrame, QMessageBox
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtGui import QFont

from ui.theme import COLORS


class HotkeyCapture(QPushButton):
    """
    熱鍵捕獲按鈕
    點擊後啟動獨立監聽，按下任意鍵或組合鍵後自動填入
    """
    hotkey_captured = pyqtSignal(str)

    def __init__(self, current: str = "", parent=None):
        super().__init__(parent)
        self._hotkey = current
        self._listening = False
        self._listener = None
        self._pressed_mods: Set[str] = set()
        self._update_display()
        self.setFixedHeight(38)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.clicked.connect(self._toggle_listen)

    def _update_display(self):
        if self._listening:
            mods_str = " + ".join([m.upper() for m in sorted(self._pressed_mods)])
            if mods_str:
                self.setText(f"⌨  {mods_str} + 請按主鍵...")
            else:
                self.setText("⌨  請按下任意鍵或組合鍵...")
            self.setStyleSheet(f"""
                QPushButton {{
                    background: {COLORS['bg_input']};
                    border: 2px solid {COLORS['accent']};
                    border-radius: 6px;
                    color: {COLORS['accent']};
                    font-size: 13px;
                    font-weight: bold;
                    text-align: center;
                }}
            """)
        else:
            if self._hotkey:
                self.setText(f"⌨  {self._hotkey.upper()}")
            else:
                self.setText("點擊以設定快捷鍵...")
            self.setStyleSheet(f"""
                QPushButton {{
                    background: {COLORS['bg_input']};
                    border: 1px solid {COLORS['border_bright']};
                    border-radius: 6px;
                    color: {COLORS['text_primary']};
                    font-size: 13px;
                    text-align: center;
                }}
                QPushButton:hover {{
                    border: 1px solid {COLORS['accent']};
                    color: {COLORS['accent']};
                }}
            """)

    def _toggle_listen(self):
        if not self._listening:
            self._start_listening()
        else:
            self._stop_listening(None)

    def _start_listening(self):
        self._listening = True
        self._pressed_mods.clear()
        self._update_display()

        # 啟動 pynput 監聽
        from pynput import keyboard

        def on_press(key):
            if not self._listening:
                return False

            # 判斷修飾鍵
            if key in (keyboard.Key.ctrl, keyboard.Key.ctrl_l, keyboard.Key.ctrl_r):
                self._pressed_mods.add("ctrl")
                QTimer.singleShot(0, self._update_display)
                return True
            if key in (keyboard.Key.alt, keyboard.Key.alt_l, keyboard.Key.alt_r, keyboard.Key.alt_gr):
                self._pressed_mods.add("alt")
                QTimer.singleShot(0, self._update_display)
                return True
            if key in (keyboard.Key.shift, keyboard.Key.shift_l, keyboard.Key.shift_r):
                self._pressed_mods.add("shift")
                QTimer.singleShot(0, self._update_display)
                return True
            if key in (keyboard.Key.cmd, keyboard.Key.cmd_l, keyboard.Key.cmd_r):
                self._pressed_mods.add("win")
                QTimer.singleShot(0, self._update_display)
                return True

            # 主鍵識別
            key_name = ""
            if hasattr(key, "name") and key.name:
                key_name = key.name.lower()
            elif hasattr(key, "char") and key.char:
                key_name = key.char.lower()
            else:
                s = str(key).replace("'", "").lower()
                key_name = s

            if not key_name:
                return True

            # 整理修飾鍵順序
            parts = []
            for m in ["ctrl", "alt", "shift", "win"]:
                if m in self._pressed_mods:
                    parts.append(m)
            parts.append(key_name)
            final_hotkey = "+".join(parts)

            QTimer.singleShot(0, lambda: self._stop_listening(final_hotkey))
            return False

        def on_release(key):
            if not self._listening:
                return False
            if key in (keyboard.Key.ctrl, keyboard.Key.ctrl_l, keyboard.Key.ctrl_r):
                self._pressed_mods.discard("ctrl")
                QTimer.singleShot(0, self._update_display)
            elif key in (keyboard.Key.alt, keyboard.Key.alt_l, keyboard.Key.alt_r, keyboard.Key.alt_gr):
                self._pressed_mods.discard("alt")
                QTimer.singleShot(0, self._update_display)
            elif key in (keyboard.Key.shift, keyboard.Key.shift_l, keyboard.Key.shift_r):
                self._pressed_mods.discard("shift")
                QTimer.singleShot(0, self._update_display)
            elif key in (keyboard.Key.cmd, keyboard.Key.cmd_l, keyboard.Key.cmd_r):
                self._pressed_mods.discard("win")
                QTimer.singleShot(0, self._update_display)
            return True

        self._listener = keyboard.Listener(on_press=on_press, on_release=on_release)
        self._listener.daemon = True
        self._listener.start()

    def _stop_listening(self, hotkey_str: Optional[str]):
        self._listening = False
        if self._listener:
            try:
                self._listener.stop()
            except Exception:
                pass
            self._listener = None

        if hotkey_str:
            self._hotkey = hotkey_str
            self.hotkey_captured.emit(hotkey_str)

        self._update_display()

    def get_hotkey(self) -> str:
        return self._hotkey

    def set_hotkey(self, hk: str):
        self._hotkey = hk
        self._update_display()

    def clear_hotkey(self):
        self._hotkey = ""
        self._stop_listening(None)


class HotkeyDialog(QDialog):
    """全域熱鍵管理對話框"""

    def __init__(
        self,
        current_start_pause: str = "Ctrl+F1",
        current_record_toggle: str = "Ctrl+F2",
        current_stop: str = "F12",
        parent=None
    ):
        super().__init__(parent)
        self.setWindowTitle("全域熱鍵設定")
        self.setModal(True)
        self.setFixedWidth(460)

        self._start_pause = current_start_pause or "Ctrl+F1"
        self._record_toggle = current_record_toggle or "Ctrl+F2"
        self._stop = current_stop or "F12"

        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.setContentsMargins(22, 22, 22, 22)

        title = QLabel("⌨  全域快捷鍵設定")
        title.setStyleSheet(f"color: {COLORS['accent']}; font-size: 15px; font-weight: bold;")
        layout.addWidget(title)

        hint = QLabel("熱鍵在遊戲視窗前後台皆可即時響應。點擊欄位後按下鍵盤組合即可自動錄入。")
        hint.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 11px;")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"background: {COLORS['border']};")
        layout.addWidget(sep)

        # 1. 開始 / 暫停執行
        row1_header = QHBoxLayout()
        row1_header.addWidget(QLabel("▶ / ⏸  開始 / 暫停執行熱鍵 (*必填)"))
        clr1 = QPushButton("清空")
        clr1.setFixedSize(46, 22)
        clr1.setStyleSheet("font-size: 11px; padding: 2px;")
        row1_header.addWidget(clr1)
        layout.addLayout(row1_header)

        self._cap_start = HotkeyCapture(self._start_pause, self)
        clr1.clicked.connect(lambda: (self._cap_start.clear_hotkey(), setattr(self, "_start_pause", "")))
        self._cap_start.hotkey_captured.connect(lambda k: setattr(self, "_start_pause", k))
        layout.addWidget(self._cap_start)

        # 2. 開始 / 結束錄製
        row2_header = QHBoxLayout()
        row2_header.addWidget(QLabel("⏺ / ⏹  開始 / 結束錄製熱鍵 (*必填)"))
        clr2 = QPushButton("清空")
        clr2.setFixedSize(46, 22)
        clr2.setStyleSheet("font-size: 11px; padding: 2px;")
        row2_header.addWidget(clr2)
        layout.addLayout(row2_header)

        self._cap_record = HotkeyCapture(self._record_toggle, self)
        clr2.clicked.connect(lambda: (self._cap_record.clear_hotkey(), setattr(self, "_record_toggle", "")))
        self._cap_record.hotkey_captured.connect(lambda k: setattr(self, "_record_toggle", k))
        layout.addWidget(self._cap_record)

        # 3. 強制停止執行
        row3_header = QHBoxLayout()
        row3_header.addWidget(QLabel("⏹  強制停止執行熱鍵 (選填)"))
        clr3 = QPushButton("清空")
        clr3.setFixedSize(46, 22)
        clr3.setStyleSheet("font-size: 11px; padding: 2px;")
        row3_header.addWidget(clr3)
        layout.addLayout(row3_header)

        self._cap_stop = HotkeyCapture(self._stop, self)
        clr3.clicked.connect(lambda: (self._cap_stop.clear_hotkey(), setattr(self, "_stop", "")))
        self._cap_stop.hotkey_captured.connect(lambda k: setattr(self, "_stop", k))
        layout.addWidget(self._cap_stop)

        # 衝突提示訊息
        self._conflict_lbl = QLabel("")
        self._conflict_lbl.setStyleSheet(f"color: {COLORS['error']}; font-size: 12px; font-weight: bold;")
        layout.addWidget(self._conflict_lbl)

        layout.addStretch()

        # 底部確定 / 取消
        btn_box = QHBoxLayout()
        btn_cancel = QPushButton("取消")
        btn_cancel.clicked.connect(self.reject)
        btn_ok = QPushButton("確認儲存")
        btn_ok.setObjectName("btn_accent")
        btn_ok.setStyleSheet("padding: 8px 20px; font-weight: bold;")
        btn_ok.clicked.connect(self._validate_and_accept)

        btn_box.addStretch()
        btn_box.addWidget(btn_cancel)
        btn_box.addWidget(btn_ok)
        layout.addLayout(btn_box)

    def _validate_and_accept(self):
        k1 = self._cap_start.get_hotkey().strip().lower()
        k2 = self._cap_record.get_hotkey().strip().lower()
        k3 = self._cap_stop.get_hotkey().strip().lower()

        if not k1:
            self._conflict_lbl.setText("⚠️ 請設定「開始/暫停執行」熱鍵！")
            return
        if not k2:
            self._conflict_lbl.setText("⚠️ 請設定「開始/結束錄製」熱鍵！")
            return

        # 衝突檢查
        if k1 == k2:
            self._conflict_lbl.setText("⚠️ 執行熱鍵 與 錄製熱鍵 不能設定為同一個鍵！")
            return
        if k3 and (k3 == k1 or k3 == k2):
            self._conflict_lbl.setText("⚠️ 強制停止熱鍵 不能與其他熱鍵重複！")
            return

        self._start_pause = self._cap_start.get_hotkey()
        self._record_toggle = self._cap_record.get_hotkey()
        self._stop = self._cap_stop.get_hotkey()

        self.accept()

    def get_hotkeys(self) -> dict:
        return {
            "start_pause": self._start_pause,
            "record_toggle": self._record_toggle,
            "stop": self._stop,
        }
