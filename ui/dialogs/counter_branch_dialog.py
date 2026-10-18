"""
Scratch 形式 If-Else 條件判斷分支對話框 (區域變數比較大小模式)
- 參照 Scratch 經典綠色六角形積木視覺設計 ( ( ) > 50, ( ) < 50, ( ) = 50 等 )
- 支援左側功能積木庫點選直接套用比較條件
- 自定義區域變數名稱與初始值 (預設為 0)
- 可選定區域變數作用範圍並在節點圖中標示結束消除位置
"""
from __future__ import annotations
from typing import Optional, List
from copy import deepcopy

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QLineEdit, QDoubleSpinBox, QComboBox,
    QGroupBox, QWidget, QFrame, QScrollArea
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QColor, QPainter, QPainterPath

from models.node import MacroNode, NodeType
from ui.theme import COLORS


class ScratchBlockWidget(QFrame):
    """
    Scratch 經典綠色六角形/圓角條件積木按鈕
    """
    clicked = pyqtSignal(str, object)  # (block_type, payload)

    def __init__(self, title: str, block_type: str, payload: object = None, parent=None):
        super().__init__(parent)
        self.block_type = block_type
        self.payload = payload
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(38)
        self.setStyleSheet("""
            QFrame {
                background-color: #59C059;
                border: 2px solid #389438;
                border-radius: 19px;
            }
            QFrame:hover {
                background-color: #68D668;
                border-color: #2F7C2F;
            }
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 0, 14, 0)
        layout.setSpacing(6)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # 內部白色藥丸型孔
        lbl_left_hole = QLabel("  ")
        lbl_left_hole.setFixedSize(30, 22)
        lbl_left_hole.setStyleSheet("background: #FFFFFF; border-radius: 11px;")
        layout.addWidget(lbl_left_hole)

        lbl_text = QLabel(title)
        lbl_text.setStyleSheet("color: #2E502E; font-size: 15px; font-weight: 900; background: transparent;")
        lbl_text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(lbl_text)

        lbl_right_hole = QLabel("  ")
        lbl_right_hole.setFixedSize(30, 22)
        lbl_right_hole.setStyleSheet("background: #FFFFFF; border-radius: 11px;")
        layout.addWidget(lbl_right_hole)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.block_type, self.payload)
        super().mousePressEvent(event)


class CounterBranchDialog(QDialog):
    """
    Scratch 形式 If-Else 條件分支設定面板 (區域變數比較大小)
    """
    def __init__(self, node: MacroNode, all_nodes: Optional[List[MacroNode]] = None, parent=None):
        super().__init__(parent)
        self._node = deepcopy(node)
        self._all_nodes = all_nodes or []

        # 若未傳入 all_nodes，嘗試從 parent 取得
        if not self._all_nodes and parent and hasattr(parent, "_macro") and parent._macro:
            self._all_nodes = parent._macro.nodes

        self.setWindowTitle("🔀 設定 If-Else 條件分支 (Scratch 區域變數比較)")
        self.resize(760, 520)
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
                left: 14px;
                padding: 0 6px;
                color: {COLORS['accent']};
            }}
            QLineEdit, QDoubleSpinBox, QComboBox {{
                background-color: {COLORS['bg_input']};
                color: {COLORS['text_primary']};
                border: 1px solid {COLORS['border']};
                border-radius: 6px;
                padding: 6px 10px;
                font-size: 13px;
            }}
            QLineEdit:focus, QDoubleSpinBox:focus, QComboBox:focus {{
                border-color: #38bdf8;
            }}
        """)

        self._setup_ui()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(12)
        main_layout.setContentsMargins(18, 16, 18, 16)

        # ── 1. 頂部模式導覽 ──────────────────────────
        top_bar = QFrame()
        top_bar.setStyleSheet(f"background: {COLORS['bg_secondary']}; border: 1px solid {COLORS['border']}; border-radius: 8px;")
        tb_layout = QHBoxLayout(top_bar)
        tb_layout.setContentsMargins(16, 10, 16, 10)
        tb_layout.setSpacing(14)

        icon_lbl = QLabel("💎")
        icon_lbl.setStyleSheet("font-size: 22px;")
        tb_layout.addWidget(icon_lbl)

        mode_title = QLabel("判斷模式：Scratch 區域變數比較大小 (Diamond If / Else)")
        mode_title.setStyleSheet("font-size: 14px; font-weight: bold; color: #4ade80;")
        tb_layout.addWidget(mode_title)

        tb_layout.addStretch()
        main_layout.addWidget(top_bar)

        # ── 2. 中間工作區：左側 Scratch 積木庫 + 右側設定面板 ─────
        content_layout = QHBoxLayout()
        content_layout.setSpacing(14)

        # ── 左側：Scratch 綠色功能方塊庫 ──
        left_toolbox = QGroupBox("🧩 Scratch 功能方塊 (點擊套用)")
        left_toolbox.setFixedWidth(260)
        lt_layout = QVBoxLayout(left_toolbox)
        lt_layout.setSpacing(10)
        lt_layout.setContentsMargins(12, 16, 12, 12)

        lt_hint = QLabel("點擊下方綠色積木，可快速將條件帶入右側設定：")
        lt_hint.setStyleSheet("color: #94a3b8; font-size: 11px;")
        lt_hint.setWordWrap(True)
        lt_layout.addWidget(lt_hint)

        # 建立積木群組 (Scratch 六角形比較積木)
        b_gt = ScratchBlockWidget("  >  50", "compare_op", ">")
        b_gt.clicked.connect(self._on_scratch_block_clicked)
        lt_layout.addWidget(b_gt)

        b_lt = ScratchBlockWidget("  <  50", "compare_op", "<")
        b_lt.clicked.connect(self._on_scratch_block_clicked)
        lt_layout.addWidget(b_lt)

        b_eq = ScratchBlockWidget("  =  50", "compare_op", "==")
        b_eq.clicked.connect(self._on_scratch_block_clicked)
        lt_layout.addWidget(b_eq)

        b_gte = ScratchBlockWidget("  >= 50", "compare_op", ">=")
        b_gte.clicked.connect(self._on_scratch_block_clicked)
        lt_layout.addWidget(b_gte)

        b_lte = ScratchBlockWidget("  <= 50", "compare_op", "<=")
        b_lte.clicked.connect(self._on_scratch_block_clicked)
        lt_layout.addWidget(b_lte)

        b_neq = ScratchBlockWidget("  != 50", "compare_op", "!=")
        b_neq.clicked.connect(self._on_scratch_block_clicked)
        lt_layout.addWidget(b_neq)

        lt_layout.addStretch()
        content_layout.addWidget(left_toolbox)

        # ── 右側：屬性設定面板 (含區域變數 + 比較條件 + 結束位置) ──
        right_panel = QWidget()
        rp_layout = QVBoxLayout(right_panel)
        rp_layout.setContentsMargins(0, 0, 0, 0)
        rp_layout.setSpacing(10)

        # (A) 區域變數定義區
        gb_var = QGroupBox("1. 區域變數定義 (Local Variable)")
        v_layout = QHBoxLayout(gb_var)
        v_layout.setSpacing(12)
        v_layout.setContentsMargins(14, 16, 14, 12)

        lbl_vn = QLabel("變數名稱：")
        self._edit_var = QLineEdit(getattr(self._node, "var_name", "X") or "X")
        self._edit_var.setFixedWidth(80)
        self._edit_var.setToolTip("自訂區域變數名稱，例如 X, count, score")

        lbl_vi = QLabel("初始值 (預設為 0)：")
        self._spin_init_val = QDoubleSpinBox()
        self._spin_init_val.setRange(-99999.0, 99999.0)
        self._spin_init_val.setValue(float(getattr(self._node, "var_init_val", 0.0)))
        self._spin_init_val.setFixedWidth(90)

        v_layout.addWidget(lbl_vn)
        v_layout.addWidget(self._edit_var)
        v_layout.addWidget(lbl_vi)
        v_layout.addWidget(self._spin_init_val)
        v_layout.addStretch()
        rp_layout.addWidget(gb_var)

        # (B) Scratch 比較條件插槽
        gb_comp = QGroupBox("2. 🔢 區域變數比較大小判斷 (Scratch 六角比較積木)")
        gc_layout = QVBoxLayout(gb_comp)
        gc_layout.setSpacing(12)
        gc_layout.setContentsMargins(14, 16, 14, 14)

        # 仿 Scratch 視覺綠色條件插槽
        scratch_slot = QFrame()
        scratch_slot.setStyleSheet("""
            QFrame {
                background-color: #59C059;
                border: 2px solid #2F7C2F;
                border-radius: 24px;
                padding: 6px 16px;
            }
        """)
        ss_layout = QHBoxLayout(scratch_slot)
        ss_layout.setSpacing(10)
        ss_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # 變數藥丸
        self._lbl_slot_var = QLabel(self._edit_var.text())
        self._lbl_slot_var.setStyleSheet("""
            background: #FFFFFF; color: #1E293B; font-weight: 900;
            font-size: 14px; border-radius: 12px; padding: 4px 14px;
        """)
        ss_layout.addWidget(self._lbl_slot_var)

        # 比較運算子下拉
        self._combo_op = QComboBox()
        self._combo_op.addItems([">", "<", "=", ">=", "<=", "!="])
        self._combo_op.setStyleSheet("""
            QComboBox {
                background: #459C45; color: #FFFFFF; font-weight: 900;
                font-size: 16px; border: 1px solid #2F7C2F; border-radius: 8px;
                padding: 4px 12px;
            }
        """)
        curr_op = getattr(self._node, "compare_op", ">")
        if curr_op == "==":
            curr_op = "="
        self._combo_op.setCurrentText(curr_op)
        ss_layout.addWidget(self._combo_op)

        # 目標數值
        self._spin_comp_target = QDoubleSpinBox()
        self._spin_comp_target.setRange(-99999.0, 99999.0)
        self._spin_comp_target.setValue(float(getattr(self._node, "compare_target", 50.0)))
        self._spin_comp_target.setStyleSheet("""
            QDoubleSpinBox {
                background: #FFFFFF; color: #1E293B; font-weight: 900;
                font-size: 14px; border-radius: 12px; padding: 4px 10px;
            }
        """)
        self._spin_comp_target.setFixedWidth(100)
        ss_layout.addWidget(self._spin_comp_target)

        gc_layout.addWidget(scratch_slot)

        lbl_comp_desc = QLabel(
            "提示：若變數滿足條件，將走【右側 If 路線】；\n"
            "若不滿足條件，將走【上方 Else 路線】。"
        )
        lbl_comp_desc.setStyleSheet("color: #94a3b8; font-size: 11px;")
        gc_layout.addWidget(lbl_comp_desc)
        rp_layout.addWidget(gb_comp)

        # (C) 區域範圍與結束位置標示
        gb_scope = QGroupBox("3. 🏁 區域變數之區域範圍 (在節點圖中標示結束位置)")
        s_layout = QVBoxLayout(gb_scope)
        s_layout.setSpacing(6)
        s_layout.setContentsMargins(14, 16, 14, 12)

        s_desc = QLabel("選擇此區域變數的作用範圍結束節點，系統將在畫布中繪製發光作用區間並標記結束位置：")
        s_desc.setStyleSheet("color: #94a3b8; font-size: 11px;")
        s_layout.addWidget(s_desc)

        row_scope = QHBoxLayout()
        lbl_scope = QLabel("結束消除位置：")
        self._combo_end_node = QComboBox()
        self._combo_end_node.addItem("(無固定結束節點，持續作用至腳本結尾)", "")

        curr_end_id = getattr(self._node, "var_scope_end_node_id", None)
        selected_idx = 0
        letters = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        for i, n in enumerate(self._all_nodes):
            if n.id != self._node.id:
                lbl = letters[i] if i < len(letters) else f"{i+1}"
                txt = f"節點 [{lbl}] : {n.get_display_name()[:20]}"
                self._combo_end_node.addItem(txt, n.id)
                if curr_end_id and n.id == curr_end_id:
                    selected_idx = self._combo_end_node.count() - 1

        self._combo_end_node.setCurrentIndex(selected_idx)
        row_scope.addWidget(lbl_scope)
        row_scope.addWidget(self._combo_end_node, stretch=1)
        s_layout.addLayout(row_scope)

        rp_layout.addWidget(gb_scope)
        content_layout.addWidget(right_panel, stretch=1)
        main_layout.addLayout(content_layout)

        # ── 3. 底部動作說明與確認按鈕 ────────────────────────
        bot_bar = QHBoxLayout()
        bot_bar.setContentsMargins(0, 6, 0, 0)

        lbl_branch_hint = QLabel("💎 菱形分支流向：滿足條件 ➔ 右頂點 (If)  |  不滿足 ➔ 上頂點折線 (Else)")
        lbl_branch_hint.setStyleSheet("color: #f59e0b; font-weight: bold; font-size: 12px;")
        bot_bar.addWidget(lbl_branch_hint)

        bot_bar.addStretch()

        btn_save = QPushButton("確認儲存")
        btn_save.setStyleSheet("""
            QPushButton {
                background: #0284c7; color: white; font-weight: bold;
                padding: 8px 22px; border-radius: 6px; font-size: 13px;
            }
            QPushButton:hover { background: #0369a1; }
        """)
        btn_save.clicked.connect(self._save_and_close)

        btn_cancel = QPushButton("取消")
        btn_cancel.setStyleSheet("""
            QPushButton {
                background: #334155; color: #cbd5e1;
                padding: 8px 18px; border-radius: 6px; font-size: 13px;
            }
            QPushButton:hover { background: #475569; }
        """)
        btn_cancel.clicked.connect(self.reject)

        bot_bar.addWidget(btn_save)
        bot_bar.addWidget(btn_cancel)
        main_layout.addLayout(bot_bar)

        # 變數名同步更新至綠色積木
        self._edit_var.textChanged.connect(lambda txt: self._lbl_slot_var.setText(txt or "X"))

    def _on_scratch_block_clicked(self, block_type: str, payload: object):
        """點擊左側 Scratch 積木時填入右側設定"""
        if block_type == "compare_op":
            op = str(payload)
            if op == "==":
                op = "="
            self._combo_op.setCurrentText(op)

    def _save_and_close(self):
        # 儲存純粹 Scratch 變數比較模式
        self._node.branch_mode = "compare"
        self._node.var_name = self._edit_var.text().strip() or "X"
        self._node.var_init_val = self._spin_init_val.value()

        op_text = self._combo_op.currentText()
        if op_text == "=":
            op_text = "=="
        self._node.compare_op = op_text
        self._node.compare_target = self._spin_comp_target.value()

        # 結束節點 ID
        end_id = self._combo_end_node.currentData()
        self._node.var_scope_end_node_id = end_id if end_id else None

        self.accept()

    def get_node(self) -> MacroNode:
        return self._node

