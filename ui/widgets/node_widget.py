"""
巨集節點卡片 Widget (AOV 圓圈節點流視圖)
以圓圈頂點 (Circle Vertex) 與向下方向箭頭 (Directed Arrow) 展示單一動作節點
支援 Root、Node、Leaf 流程層級標識與執行即時高亮
"""
from __future__ import annotations
from typing import Optional

from ui.qt_compat import (
    QtWidgets, QtCore, QtGui, Qt
)
from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QLabel, QPushButton, QFrame
)
from PyQt6.QtCore import Qt, pyqtSignal, QPoint, QRect, QSize
from PyQt6.QtGui import QPainter, QColor, QPen, QBrush, QFont, QPolygon

from models.node import MacroNode, NodeType
from ui.theme import COLORS, get_node_style, NODE_ICONS


class AovIndicatorWidget(QWidget):
    """
    AOV 圖圓圈頂點與方向箭頭繪製器
    繪製：上引線 -> 圓圈頂點 (帶序號/字母) -> 下引線與方向箭頭 ▼
    """

    def __init__(
        self,
        index: int = 0,
        total: int = 1,
        node_type: NodeType = NodeType.KEY_CLICK,
        parent=None
    ):
        super().__init__(parent)
        self._index = index
        self._total = total
        self._node_type = node_type
        self._is_executing = False
        self.setFixedWidth(54)
        self.setMinimumHeight(66)

    def set_index(self, index: int, total: int):
        self._index = index
        self._total = total
        self.update()

    def set_executing(self, executing: bool):
        self._is_executing = executing
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = self.width()
        h = self.height()
        cx = w // 2
        cy = h // 2
        radius = 16

        # 決定節點色彩（採用高對比鮮亮色系）
        t_str = self._node_type.value if hasattr(self._node_type, "value") else str(self._node_type)
        if "GAMEPAD" in t_str:
            circle_color = QColor("#c084fc")  # 搖桿：亮粉紫
            border_color = QColor("#a855f7")
        elif "KEY" in t_str:
            circle_color = QColor("#38bdf8")  # 鍵盤：天藍
            border_color = QColor("#0284c7")
        elif "MOUSE" in t_str:
            circle_color = QColor("#34d399")  # 滑鼠：薄荷綠
            border_color = QColor("#059669")
        elif "WAIT" in t_str:
            circle_color = QColor("#fbbf24")  # 等待：琥珀金
            border_color = QColor("#d97706")
        else:
            circle_color = QColor("#94a3b8")  # 其他：冷灰
            border_color = QColor("#64748b")

        line_color = QColor("#38bdf8") if not self._is_executing else QColor("#facc15")
        pen_line = QPen(line_color, 2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)

        # 1. 頂部引線（非第 0 個節點才繪製由上方連接過來的線）
        if self._index > 0:
            painter.setPen(pen_line)
            painter.drawLine(cx, 0, cx, cy - radius)

        # 2. 執行中光暈
        if self._is_executing:
            glow_color = QColor(250, 204, 21, 100)
            painter.setBrush(QBrush(glow_color))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(QPoint(cx, cy), radius + 6, radius + 6)
            circle_color = QColor("#fde047")
            border_color = QColor("#ca8a04")

        # 3. 繪製中央圓圈頂點 (Circle Vertex)
        painter.setBrush(QBrush(circle_color))
        painter.setPen(QPen(border_color, 2))
        painter.drawEllipse(QPoint(cx, cy), radius, radius)

        # 4. 圓圈內繪製文字（序號如 01, 02 或字母 A, B, C）
        # 依使用者圖示，顯示 A, B, C 或兩位序號
        letters = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        label_text = letters[self._index] if self._index < len(letters) else f"{self._index + 1:02d}"

        painter.setPen(QColor("#0f172a"))  # 黑色粗體，極高對比
        font = QFont("Consolas", 11, QFont.Weight.Bold)
        painter.setFont(font)
        text_rect = QRect(cx - radius, cy - radius, radius * 2, radius * 2)
        painter.drawText(text_rect, Qt.AlignmentFlag.AlignCenter, label_text)

        # 5. 底部引線與向下方向箭頭 (Directed Arrow)
        # 即使是最後一個節點，也向下畫出指向下一個新增點的箭頭
        arrow_bottom = h
        painter.setPen(pen_line)
        painter.drawLine(cx, cy + radius, cx, arrow_bottom - 6)

        # 繪製向下箭頭 ▼
        arrow_pts = [
            QPoint(cx - 5, arrow_bottom - 7),
            QPoint(cx + 5, arrow_bottom - 7),
            QPoint(cx, arrow_bottom - 1),
        ]
        painter.setBrush(QBrush(line_color))
        painter.drawPolygon(QPolygon(arrow_pts))


class NodeWidget(QWidget):
    """
    AOV 巨集動作節點卡片
    左側：圓圈頂點 + 拓撲向下方向箭頭
    右側：結構化動作資訊膠囊與操作按鈕
    """
    delete_requested   = pyqtSignal(object)    # 傳 node
    copy_requested     = pyqtSignal(object)    # 傳 node
    edit_requested     = pyqtSignal(object)    # 傳 node

    def __init__(self, node: MacroNode, index: int = 0, total: int = 1, parent=None):
        super().__init__(parent)
        self._node = node
        self._index = index
        self._total = total
        self._setup_ui()

    def _setup_ui(self):
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(4, 2, 8, 2)
        main_layout.setSpacing(6)

        # ── 左側：AOV 圓圈頂點與方向箭頭指示器 ─────────────────
        self.indicator = AovIndicatorWidget(
            index=self._index,
            total=self._total,
            node_type=self._node.type,
            parent=self
        )
        main_layout.addWidget(self.indicator)

        # ── 右側：動作主卡片 ──────────────────────────────────
        card = QFrame()
        bg, border = get_node_style(self._node.type)
        card.setObjectName("node_card")
        card.setStyleSheet(f"""
            QFrame#node_card {{
                background-color: #161f30;
                border: 1px solid #2a3b5c;
                border-radius: 8px;
            }}
            QFrame#node_card:hover {{
                border: 1px solid {COLORS['accent']};
                background-color: #1b2840;
            }}
        """)
        card_layout = QHBoxLayout(card)
        card_layout.setContentsMargins(10, 8, 10, 8)
        card_layout.setSpacing(8)

        # 1. 角色標籤 (Root, Branch, Node, Leaf) 呼應使用者樹/AOV概念
        role_text = "NODE"
        role_color = "#38bdf8"
        role_bg = "#0c4a6e"
        if self._index == 0 and self._total == 1:
            role_text = "ROOT"
            role_color = "#4ade80"
            role_bg = "#064e3b"
        elif self._index == 0:
            role_text = "ROOT"
            role_color = "#38bdf8"
            role_bg = "#0369a1"
        elif self._index == self._total - 1:
            role_text = "LEAF"
            role_color = "#a78bfa"
            role_bg = "#4c1d95"

        lbl_role = QLabel(f"➔ {role_text}")
        lbl_role.setStyleSheet(f"""
            font-size: 9px;
            font-weight: bold;
            color: {role_color};
            background-color: {role_bg};
            padding: 2px 5px;
            border-radius: 3px;
        """)
        lbl_role.setFixedHeight(18)
        card_layout.addWidget(lbl_role)

        # 2. 動作圖示
        icon = NODE_ICONS.get(self._node.type, "?")
        lbl_icon = QLabel(icon)
        lbl_icon.setStyleSheet("font-size: 16px;")
        card_layout.addWidget(lbl_icon)

        # 3. 動作詳細描述與參數
        info_layout = QVBoxLayout()
        info_layout.setSpacing(2)
        info_layout.setContentsMargins(0, 0, 0, 0)

        title_text = self._node.get_display_name()
        lbl_title = QLabel(title_text)
        lbl_title.setStyleSheet(f"""
            color: {COLORS['text_primary']};
            font-size: 12px;
            font-weight: bold;
            font-family: Consolas, monospace;
        """)
        info_layout.addWidget(lbl_title)

        # 附加時間戳與註解
        sub_info = []
        if getattr(self._node, "timestamp_ms", 0) > 0:
            sub_info.append(f"時間: +{self._node.timestamp_ms}ms")
        if self._node.comment:
            sub_info.append(f"備註: {self._node.comment}")

        if sub_info:
            lbl_sub = QLabel(" | ".join(sub_info))
            lbl_sub.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 10px;")
            info_layout.addWidget(lbl_sub)

        card_layout.addLayout(info_layout, stretch=1)


        # 5. 操作按鈕（編輯、複製、刪除）
        btn_style = f"""
            QPushButton {{
                background: transparent;
                border: none;
                color: {COLORS['text_dim']};
                font-size: 13px;
                min-width: 22px;
                max-width: 22px;
                min-height: 22px;
                max-height: 22px;
                border-radius: 3px;
            }}
            QPushButton:hover {{
                background: {COLORS['bg_hover']};
                color: {COLORS['text_primary']};
            }}
        """

        edit_btn = QPushButton("✏")
        edit_btn.setToolTip("編輯節點屬性")
        edit_btn.setStyleSheet(btn_style)
        edit_btn.clicked.connect(lambda: self.edit_requested.emit(self._node))
        card_layout.addWidget(edit_btn)

        copy_btn = QPushButton("⧉")
        copy_btn.setToolTip("複製此節點")
        copy_btn.setStyleSheet(btn_style)
        copy_btn.clicked.connect(lambda: self.copy_requested.emit(self._node))
        card_layout.addWidget(copy_btn)

        del_btn = QPushButton("✕")
        del_btn.setToolTip("刪除此節點")
        del_btn.setStyleSheet(btn_style.replace(COLORS['text_dim'], COLORS['error']))
        del_btn.clicked.connect(lambda: self.delete_requested.emit(self._node))
        card_layout.addWidget(del_btn)

        main_layout.addWidget(card, stretch=1)

    @property
    def node(self) -> MacroNode:
        return self._node

    def update_index(self, index: int, total: int = 1):
        self._index = index
        self._total = total
        self.indicator.set_index(index, total)

    def set_executing(self, executing: bool):
        """回放執行時高亮此圓圈節點"""
        self.indicator.set_executing(executing)
