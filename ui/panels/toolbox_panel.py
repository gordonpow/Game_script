"""
側邊欄節點工具箱面板 (Toolbox Panel)
提供看門狗守護節點、雙輸出計時器分支節點與常用動作
使用者可直接拖曳 (Drag & Drop) 或點擊 [+] 快速插入至橫向 AOV 流程畫布
"""
from __future__ import annotations
from typing import Optional, Callable
import json

from ui.qt_compat import (
    QtWidgets, QtCore, QtGui, Qt
)
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFrame, QScrollArea, QListWidget, QListWidgetItem
)
from PyQt6.QtCore import Qt, pyqtSignal, QMimeData, QPoint, QRect
from PyQt6.QtGui import QDrag, QPixmap, QPainter, QColor, QFont


from models.node import MacroNode, NodeType
from ui.theme import COLORS


class DraggableNodeCard(QFrame):
    """可拖曳至 AOV 畫布的節點卡片"""
    add_clicked = pyqtSignal(str)  # 傳 node_type

    def __init__(self, node_type: str, title: str, subtitle: str, color: str, icon: str, parent=None):
        super().__init__(parent)
        self.node_type = node_type
        self.title_text = title
        self.color_hex = color
        self.icon_text = icon
        self._drag_start_pos = None

        self.setStyleSheet(f"""
            QFrame {{
                background-color: #1a1a26;
                border: 1px solid #2e2e42;
                border-left: 4px solid {color};
                border-radius: 6px;
                padding: 6px;
            }}
            QFrame:hover {{
                background-color: #242436;
                border-color: {color};
            }}
        """)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(8)

        lbl_icon = QLabel(icon)
        lbl_icon.setStyleSheet(f"font-size: 18px; color: {color};")
        layout.addWidget(lbl_icon)

        text_layout = QVBoxLayout()
        text_layout.setSpacing(2)
        lbl_t = QLabel(title)
        lbl_t.setStyleSheet("font-size: 11px; font-weight: bold; color: #ffffff;")
        lbl_t.setWordWrap(True)
        lbl_sub = QLabel(subtitle)
        lbl_sub.setStyleSheet("font-size: 10px; color: #94a3b8;")
        lbl_sub.setWordWrap(True)
        text_layout.addWidget(lbl_t)
        text_layout.addWidget(lbl_sub)
        layout.addLayout(text_layout, stretch=1)

        btn_add = QPushButton("＋")
        btn_add.setFixedSize(24, 24)
        btn_add.setToolTip("點擊直接插入此節點至主程序")
        btn_add.setStyleSheet(f"""
            QPushButton {{
                background-color: #27273a;
                color: {color};
                border: 1px solid #3b3b55;
                border-radius: 12px;
                font-weight: bold;
                font-size: 13px;
            }}
            QPushButton:hover {{
                background-color: {color};
                color: #0f172a;
            }}
        """)
        btn_add.clicked.connect(lambda: self.add_clicked.emit(self.node_type))
        layout.addWidget(btn_add)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_start_pos = event.pos()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if not (event.buttons() & Qt.MouseButton.LeftButton):
            return
        if self._drag_start_pos is None:
            return
        if (event.pos() - self._drag_start_pos).manhattanLength() < 5:
            return

        # 發起拖曳 (QDrag)
        drag = QDrag(self)
        mime_data = QMimeData()
        mime_data.setData("application/x-gamescript-node", self.node_type.encode("utf-8"))
        mime_data.setText(self.node_type)
        drag.setMimeData(mime_data)

        # 拖曳預覽圖像
        pixmap = QPixmap(160, 38)
        pixmap.fill(Qt.GlobalColor.transparent)
        p = QPainter(pixmap)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setBrush(QColor("#1e293b"))
        p.setPen(QColor(self.color_hex))
        p.drawRoundedRect(2, 2, 156, 34, 6, 6)
        p.setPen(QColor("#ffffff"))
        p.setFont(QFont("Consolas", 9, QFont.Weight.Bold))
        p.drawText(QRect(6, 2, 148, 34), Qt.AlignmentFlag.AlignCenter, f"{self.icon_text} {self.title_text}")
        p.end()

        drag.setPixmap(pixmap)
        drag.setHotSpot(QPoint(80, 19))
        drag.exec(Qt.DropAction.CopyAction)


class ToolboxPanel(QWidget):
    """側邊欄動作模組工具箱面板 (鍵盤、滑鼠、手把、延時、雙輸出分支)"""
    node_insert_requested = pyqtSignal(str)  # 傳 node_type

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(240)
        self.setStyleSheet(f"""
            ToolboxPanel {{
                background-color: {COLORS['bg_secondary']};
                border-right: 1px solid {COLORS['border']};
            }}
        """)
        self._setup_ui()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(6)

        # 頂部標題
        hdr_layout = QHBoxLayout()
        lbl_hdr = QLabel("🧩 動作模組庫")
        lbl_hdr.setStyleSheet(f"font-size: 13px; font-weight: bold; color: {COLORS['accent']};")
        hdr_layout.addWidget(lbl_hdr)
        main_layout.addLayout(hdr_layout)

        lbl_drag_tip = QLabel("拖曳至畫布或按 [＋] 插入")
        lbl_drag_tip.setStyleSheet("font-size: 11px; color: #94a3b8;")
        main_layout.addWidget(lbl_drag_tip)

        # 滾動區域
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("background: transparent; border: none;")

        container = QWidget()
        c_layout = QVBoxLayout(container)
        c_layout.setContentsMargins(0, 4, 0, 4)
        c_layout.setSpacing(6)

        # ── 1. 鍵盤模組 ──
        lbl_sec_k = QLabel("⌨️ 鍵盤動作模組")
        lbl_sec_k.setStyleSheet("font-size: 11px; font-weight: bold; color: #38bdf8; margin-top: 4px;")
        c_layout.addWidget(lbl_sec_k)

        kb_items = [
            (NodeType.KEY_CLICK, "按鍵點擊", "按下並自動釋放", "#38bdf8", "⌨"),
            (NodeType.KEY_DOWN,  "按鍵按下", "持續按住鍵位", "#0ea5e9", "⬇"),
            (NodeType.KEY_UP,    "按鍵釋放", "釋放指定鍵位", "#0284c7", "⬆"),
        ]
        for nt, t, sub, col, ic in kb_items:
            card = DraggableNodeCard(nt, t, sub, col, ic)
            card.add_clicked.connect(self.node_insert_requested.emit)
            c_layout.addWidget(card)

        # ── 2. 滑鼠模組 ──
        lbl_sec_m = QLabel("🖱️ 滑鼠動作模組")
        lbl_sec_m.setStyleSheet("font-size: 11px; font-weight: bold; color: #34d399; margin-top: 6px;")
        c_layout.addWidget(lbl_sec_m)

        mouse_items = [
            (NodeType.MOUSE_CLICK,  "滑鼠點擊", "左/右/中鍵目標點擊", "#34d399", "🖱"),
            (NodeType.MOUSE_MOVE,   "滑鼠移動", "相對視窗平滑位移", "#10b981", "🎯"),
            (NodeType.MOUSE_SCROLL, "滑鼠滾輪", "滾輪上滾/下滾", "#059669", "↕"),
        ]
        for nt, t, sub, col, ic in mouse_items:
            card = DraggableNodeCard(nt, t, sub, col, ic)
            card.add_clicked.connect(self.node_insert_requested.emit)
            c_layout.addWidget(card)

        # ── 3. 手把 / 搖桿模組 ──
        lbl_sec_g = QLabel("🎮 手把 / 搖桿模組")
        lbl_sec_g.setStyleSheet("font-size: 11px; font-weight: bold; color: #c084fc; margin-top: 6px;")
        c_layout.addWidget(lbl_sec_g)

        pad_items = [
            (NodeType.GAMEPAD_BUTTON, "手把按鍵", "A, B, X, Y, LB, RB, LT...", "#c084fc", "🎮"),
            (NodeType.GAMEPAD_AXIS,   "搖桿推桿", "左右搖桿軸向推移", "#a855f7", "🕹️"),
        ]
        for nt, t, sub, col, ic in pad_items:
            card = DraggableNodeCard(nt, t, sub, col, ic)
            card.add_clicked.connect(self.node_insert_requested.emit)
            c_layout.addWidget(card)

        # ── 4. 時間等待 ──
        lbl_sec_t = QLabel("⏱️ 時間延遲等待")
        lbl_sec_t.setStyleSheet("font-size: 11px; font-weight: bold; color: #a3e635; margin-top: 6px;")
        c_layout.addWidget(lbl_sec_t)

        wait_items = [
            (NodeType.WAIT_FIXED,  "固定等待", "精確毫秒延遲", "#a3e635", "⏱"),
            (NodeType.WAIT_RANDOM, "隨機等待", "防偵測隨機區間", "#84cc16", "🎲"),
        ]
        for nt, t, sub, col, ic in wait_items:
            card = DraggableNodeCard(nt, t, sub, col, ic)
            card.add_clicked.connect(self.node_insert_requested.emit)
            c_layout.addWidget(card)

        # ── 5. 雙輸出分支與迴圈 ──
        lbl_sec_b = QLabel("⏳ 雙輸出分支與控制")
        lbl_sec_b.setStyleSheet("font-size: 11px; font-weight: bold; color: #fbbf24; margin-top: 6px;")
        c_layout.addWidget(lbl_sec_b)

        branch_items = [
            (NodeType.COUNTER_BRANCH, "計時變數 X", "雙輸出: 達X秒觸發/繼續", "#fbbf24", "⏳"),
            (NodeType.REPEAT_BLOCK,   "重複迴圈", "重複執行子動作區塊", "#f59e0b", "↺"),
        ]
        for nt, t, sub, col, ic in branch_items:
            card = DraggableNodeCard(nt, t, sub, col, ic)
            card.add_clicked.connect(self.node_insert_requested.emit)
            c_layout.addWidget(card)

        c_layout.addStretch()
        scroll.setWidget(container)
        main_layout.addWidget(scroll, stretch=1)
