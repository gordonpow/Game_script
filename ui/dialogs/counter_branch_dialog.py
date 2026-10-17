"""
計時/計數雙輸出分支節點設定對話框
設定區域變數 X、計時秒數、以及觸發分支 (按鍵放開/特定動作) 與未觸發分支動作
"""
from __future__ import annotations
from typing import Optional
from copy import deepcopy

from ui.qt_compat import (
    QtWidgets, QtCore, QtGui, Qt
)
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QLineEdit, QDoubleSpinBox, QComboBox,
    QGroupBox, QListWidget, QListWidgetItem, QMessageBox, QFrame
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

from models.node import MacroNode, NodeType
from ui.theme import COLORS


class CounterBranchDialog(QDialog):
    """計時變數 X 雙輸出分支設定對話框"""

    def __init__(self, node: MacroNode, parent=None):
        super().__init__(parent)
        self._node = deepcopy(node)
        self.setWindowTitle("⏳ 設定計數/計時器雙輸出分支節點")
        self.setMinimumWidth(500)
        self.setMinimumHeight(460)
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
                margin-top: 14px;
                padding-top: 16px;
                background-color: {COLORS['bg_secondary']};
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 6px;
                color: {COLORS['accent']};
            }}
            QLineEdit, QDoubleSpinBox, QComboBox {{
                background-color: {COLORS['bg_input']};
                color: {COLORS['text_primary']};
                border: 1px solid {COLORS['border']};
                border-radius: 4px;
                padding: 6px;
                font-size: 13px;
            }}
            QLineEdit:focus, QDoubleSpinBox:focus, QComboBox:focus {{
                border-color: {COLORS['accent']};
            }}
        """)

        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.setContentsMargins(18, 18, 18, 18)

        # 頂部說明
        title_lbl = QLabel("⏳ 區域變數計時器 (雙輸出分支)")
        title_lbl.setStyleSheet("font-size: 16px; font-weight: bold; color: #ffffff;")
        layout.addWidget(title_lbl)

        desc_lbl = QLabel(
            "當此節點生成時，將啟動區域變數計時。當達到 X 秒 (或條件滿足) 時，執行【觸發分支】；\n"
            "若時間尚未到達，則繼續執行【未觸發分支】常態流程。"
        )
        desc_lbl.setStyleSheet("color: #94a3b8; font-size: 11px;")
        desc_lbl.setWordWrap(True)
        layout.addWidget(desc_lbl)

        # ── 參數設定群組 ──
        gb_params = QGroupBox("1. 區域變數與計時參數")
        p_layout = QHBoxLayout(gb_params)
        p_layout.setSpacing(12)

        # 變數名
        lbl_v = QLabel("變數名稱：")
        lbl_v.setStyleSheet("font-weight: bold;")
        self._edit_var = QLineEdit(getattr(self._node, "var_name", "X") or "X")
        self._edit_var.setFixedWidth(60)
        p_layout.addWidget(lbl_v)
        p_layout.addWidget(self._edit_var)

        # 計時秒數
        lbl_s = QLabel("目標時長 (秒)：")
        lbl_s.setStyleSheet("font-weight: bold;")
        self._spin_sec = QDoubleSpinBox()
        self._spin_sec.setRange(0.1, 999.0)
        self._spin_sec.setSingleStep(0.5)
        self._spin_sec.setValue(float(getattr(self._node, "timer_seconds", 3.0) or 3.0))
        self._spin_sec.setSuffix(" 秒")
        p_layout.addWidget(lbl_s)
        p_layout.addWidget(self._spin_sec)

        p_layout.addStretch()
        layout.addWidget(gb_params)

        # ── 分支 1: 觸發時執行的操作 (時間到 / 按鍵放開時插入) ──
        gb_trig = QGroupBox("2. ⚡ 觸發分支 (時間到達 / 按鍵放開時執行的操作)")
        t_layout = QVBoxLayout(gb_trig)
        t_layout.setSpacing(6)

        self._list_trig = QListWidget()
        self._list_trig.setStyleSheet(f"""
            QListWidget {{
                background: {COLORS['bg_input']};
                border: 1px solid #059669;
                border-radius: 4px;
                color: #ffffff;
            }}
            QListWidget::item {{ padding: 6px; }}
            QListWidget::item:selected {{ background: #064e3b; }}
        """)
        self._refresh_trigger_list()
        t_layout.addWidget(self._list_trig)

        # 快速新增觸發動作
        h_trig_btns = QHBoxLayout()
        btn_add_key_up = QPushButton("＋ 插入按鍵釋放 (Key UP)")
        btn_add_key_up.setStyleSheet("background: #047857; color: white; padding: 4px 10px; border-radius: 4px;")
        btn_add_key_up.clicked.connect(self._add_trig_key_up)

        btn_add_pad = QPushButton("＋ 插入手把按鍵 (Gamepad)")
        btn_add_pad.setStyleSheet("background: #6d28d9; color: white; padding: 4px 10px; border-radius: 4px;")
        btn_add_pad.clicked.connect(self._add_trig_gamepad)

        btn_del_trig = QPushButton("⌫ 移除選中")
        btn_del_trig.setStyleSheet("background: #334155; color: #f87171; padding: 4px 10px; border-radius: 4px;")
        btn_del_trig.clicked.connect(self._del_trig_item)

        h_trig_btns.addWidget(btn_add_key_up)
        h_trig_btns.addWidget(btn_add_pad)
        h_trig_btns.addStretch()
        h_trig_btns.addWidget(btn_del_trig)
        t_layout.addLayout(h_trig_btns)

        layout.addWidget(gb_trig)

        # ── 分支 2: 未觸發時操作 ──
        gb_cont = QGroupBox("3. ▶ 未觸發分支 (時間尚未到達時繼續的操作)")
        c_layout = QVBoxLayout(gb_cont)
        lbl_cont_info = QLabel("提示：未觸發時將自動順著主流程繼續向下執行，亦可在下方插入特定輪詢動作。")
        lbl_cont_info.setStyleSheet("color: #94a3b8; font-size: 11px;")
        c_layout.addWidget(lbl_cont_info)
        layout.addWidget(gb_cont)

        # ── 底部確認與取消 ──
        b_layout = QHBoxLayout()
        btn_save = QPushButton("確認儲存")
        btn_save.setStyleSheet("""
            QPushButton {
                background: #ea580c; color: white; font-weight: bold;
                padding: 8px 24px; border-radius: 6px; font-size: 13px;
            }
            QPushButton:hover { background: #f97316; }
        """)
        btn_save.clicked.connect(self._save_and_close)

        btn_cancel = QPushButton("取消")
        btn_cancel.setStyleSheet(f"""
            QPushButton {{
                background: {COLORS.get('bg_card', '#1A1A26')}; color: {COLORS.get('text_secondary', '#8888A0')};
                border: 1px solid {COLORS.get('border', '#2A2A3D')}; padding: 8px 18px; border-radius: 6px;
            }}
        """)
        btn_cancel.clicked.connect(self.reject)


        b_layout.addStretch()
        b_layout.addWidget(btn_save)
        b_layout.addWidget(btn_cancel)
        layout.addLayout(b_layout)

    def _refresh_trigger_list(self):
        self._list_trig.clear()
        nodes = getattr(self._node, "on_trigger_nodes", []) or []
        for n in nodes:
            item = QListWidgetItem(f"⚡ {n.get_display_name()}")
            self._list_trig.addItem(item)
        if not nodes:
            item = QListWidgetItem("(尚未設定觸發動作，請點擊下方按鈕加入)")
            item.setFlags(Qt.ItemFlag.NoItemFlags)
            self._list_trig.addItem(item)

    def _add_trig_key_up(self):
        node = MacroNode(type=NodeType.KEY_UP, key="space")
        self._node.on_trigger_nodes.append(node)
        self._refresh_trigger_list()

    def _add_trig_gamepad(self):
        node = MacroNode(type=NodeType.GAMEPAD_BUTTON, gamepad_button="A", gamepad_action="click")
        self._node.on_trigger_nodes.append(node)
        self._refresh_trigger_list()

    def _del_trig_item(self):
        row = self._list_trig.currentRow()
        if 0 <= row < len(self._node.on_trigger_nodes):
            self._node.on_trigger_nodes.pop(row)
            self._refresh_trigger_list()

    def _save_and_close(self):
        self._node.var_name = self._edit_var.text().strip() or "X"
        self._node.timer_seconds = self._spin_sec.value()
        self.accept()

    def get_node(self) -> MacroNode:
        return self._node
