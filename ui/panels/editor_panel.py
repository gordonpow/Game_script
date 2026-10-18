"""
巨集編輯器面板（右側）- 橫向 AOV 圓圈節點時間軸
以橫向單向拓撲流展示動作序列 (A ➔ B ➔ C ➔ ＋)
- 內建側邊欄看門狗與模組工具箱 (ToolboxPanel)，支援直接拖曳 (Drag & Drop) 至畫布
- 支援計數器/計時變數 X 雙輸出分支節點 (觸發/未觸發)
- 乾淨純粹的圓圈節點，滑鼠右鍵詳細操作選單 (更改鍵位、複製、刪除)
- 選中節點後按鍵盤 Delete 鍵直接刪除，雙擊進入設定
"""
from __future__ import annotations
from copy import deepcopy
from typing import List, Optional, Callable
import uuid

from ui.qt_compat import (
    QtWidgets, QtCore, QtGui, Qt
)
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFrame, QMenu, QMessageBox, QSplitter
)
from PyQt6.QtCore import Qt, pyqtSignal, QSize, QPoint

from models.node import MacroNode, NodeType
from models.macro import Macro, PlaybackMode
from ui.theme import COLORS, NODE_ICONS
from ui.widgets.horizontal_aov_widget import HorizontalAovCanvas
from ui.panels.toolbox_panel import ToolboxPanel


class EditorPanel(QWidget):
    """
    巨集編輯器面板（橫向 AOV 圓圈節點流 + 側邊欄拖曳工具箱）
    """
    macro_changed = pyqtSignal()   # 任何改動後觸發

    def __init__(self, parent=None):
        super().__init__(parent)
        self._macro: Optional[Macro] = None
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── 頂部工具列 ────────────────────────────────────────
        toolbar = QWidget()
        toolbar.setStyleSheet(f"background: {COLORS['bg_secondary']}; border-bottom: 1px solid {COLORS['border']};")
        toolbar_layout = QHBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(12, 6, 12, 6)
        toolbar_layout.setSpacing(8)

        title = QLabel("✏  橫向 AOV 動作序列畫布")
        title.setStyleSheet(f"color: {COLORS['accent']}; font-weight: bold; font-size: 13px;")
        toolbar_layout.addWidget(title)

        toolbar_layout.addSpacing(10)

        # ── 快捷新增動作按鈕組 (鍵盤 / 滑鼠 / 手把 / 等待 / 分支) ──
        btn_style_base = """
            QPushButton {
                background-color: #1e293b;
                color: %s;
                font-size: 12px;
                font-weight: bold;
                padding: 4px 10px;
                border-radius: 4px;
                border: 1px solid %s;
            }
            QPushButton:hover {
                background-color: %s;
                color: #ffffff;
            }
        """

        btn_add_k = QPushButton("⌨️  ＋鍵盤")
        btn_add_k.setStyleSheet(btn_style_base % ("#38bdf8", "#0284c7", "#0284c7"))
        btn_add_k.setToolTip("新增鍵盤按鍵點擊/按下動作")
        btn_add_k.clicked.connect(lambda: self._add_node_by_type(NodeType.KEY_CLICK))
        toolbar_layout.addWidget(btn_add_k)

        btn_add_m = QPushButton("🖱️  ＋滑鼠")
        btn_add_m.setStyleSheet(btn_style_base % ("#34d399", "#059669", "#059669"))
        btn_add_m.setToolTip("新增滑鼠點擊/移動動作")
        btn_add_m.clicked.connect(lambda: self._add_node_by_type(NodeType.MOUSE_CLICK))
        toolbar_layout.addWidget(btn_add_m)

        btn_add_g = QPushButton("🎮  ＋手把")
        btn_add_g.setStyleSheet(btn_style_base % ("#c084fc", "#9333ea", "#9333ea"))
        btn_add_g.setToolTip("新增 Xbox 搖桿按鈕/推桿動作")
        btn_add_g.clicked.connect(lambda: self._add_node_by_type(NodeType.GAMEPAD_BUTTON))
        toolbar_layout.addWidget(btn_add_g)

        btn_add_w = QPushButton("⏱️  ＋等待")
        btn_add_w.setStyleSheet(btn_style_base % ("#a3e635", "#65a30d", "#65a30d"))
        btn_add_w.setToolTip("新增時間延遲等待")
        btn_add_w.clicked.connect(lambda: self._add_node_by_type(NodeType.WAIT_FIXED))
        toolbar_layout.addWidget(btn_add_w)

        btn_add_b = QPushButton("⏳  ＋計時分支")
        btn_add_b.setStyleSheet(btn_style_base % ("#fbbf24", "#d97706", "#d97706"))
        btn_add_b.setToolTip("新增計時變數 X 雙輸出分支 (達X秒觸發/繼續)")
        btn_add_b.clicked.connect(lambda: self._add_node_by_type(NodeType.COUNTER_BRANCH))
        toolbar_layout.addWidget(btn_add_b)

        toolbar_layout.addStretch()

        self._duration_label = QLabel("AOV 節點: 0  |  估算: 0 ms")
        self._duration_label.setStyleSheet("color: #94a3b8; font-size: 12px; margin-right: 8px;")
        toolbar_layout.addWidget(self._duration_label)

        btn_layout = QPushButton("🪄  自動整隊")
        btn_layout.setToolTip("依照順序由左至右自動排列節點，消除重疊並拉直箭頭")
        btn_layout.setStyleSheet("""
            QPushButton {
                background-color: #1e293b;
                color: #38bdf8;
                font-size: 12px;
                font-weight: bold;
                padding: 4px 10px;
                border-radius: 4px;
                border: 1px solid #0284c7;
            }
            QPushButton:hover {
                background-color: #0284c7;
                color: #ffffff;
            }
        """)
        btn_layout.clicked.connect(self._auto_layout_nodes)
        toolbar_layout.addWidget(btn_layout)

        clear_btn = QPushButton("⌫  清空畫布")
        clear_btn.setObjectName("btn_danger")
        clear_btn.setStyleSheet("""
            QPushButton {
                background-color: #334155;
                color: #f87171;
                font-size: 12px;
                padding: 4px 12px;
                border-radius: 4px;
                border: 1px solid #475569;
            }
            QPushButton:hover {
                background-color: #7f1d1d;
                color: #ffffff;
            }
        """)
        clear_btn.clicked.connect(self._clear_all)
        toolbar_layout.addWidget(clear_btn)

        layout.addWidget(toolbar)

        # ── 即時狀態與操作指引列 (Live Monitor) ───────────────
        self._live_monitor = QFrame()
        self._live_monitor.setStyleSheet(f"""
            QFrame {{
                background: {COLORS['bg_card']};
                border-bottom: 1px solid {COLORS['border']};
            }}
        """)
        lm_layout = QHBoxLayout(self._live_monitor)
        lm_layout.setContentsMargins(12, 5, 12, 5)
        lm_layout.setSpacing(10)

        self._lbl_live_status = QLabel("🟢 待機中")
        self._lbl_live_status.setStyleSheet("font-weight: bold; color: #4ade80; font-size: 12px;")
        lm_layout.addWidget(self._lbl_live_status)

        self._lbl_live_action = QLabel("💡 提示：可在畫布空白處【點擊右鍵】或點擊頂部按鈕新增動作節點；拖曳節點可吸附網格，按 [Delete] 刪除")
        self._lbl_live_action.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 12px;")
        lm_layout.addWidget(self._lbl_live_action, stretch=1)

        layout.addWidget(self._live_monitor)


        # ── 中央區域：左側節點工具箱 + 右側橫向 AOV 流程畫布 ──
        center_widget = QWidget()
        center_layout = QHBoxLayout(center_widget)
        center_layout.setContentsMargins(0, 0, 0, 0)
        center_layout.setSpacing(0)

        # 1. 側邊欄：動作模組工具箱
        self._toolbox = ToolboxPanel(self)
        self._toolbox.node_insert_requested.connect(self._add_node_by_type)
        center_layout.addWidget(self._toolbox)

        # 2. 右側畫布主體容器
        canvas_container = QWidget()
        cc_layout = QVBoxLayout(canvas_container)
        cc_layout.setContentsMargins(0, 0, 0, 0)
        cc_layout.setSpacing(0)

        self._aov_canvas = HorizontalAovCanvas(self)
        self._aov_canvas.delete_requested.connect(self._delete_node)
        self._aov_canvas.copy_requested.connect(self._copy_node)
        self._aov_canvas.edit_requested.connect(self._edit_node)
        self._aov_canvas.add_node_requested.connect(self._show_add_menu)
        self._aov_canvas.add_node_at_pos_requested.connect(self._add_node_at_pos)
        self._aov_canvas.node_dropped.connect(self._add_node_by_type)
        self._aov_canvas.macro_modified.connect(self.macro_changed.emit)
        cc_layout.addWidget(self._aov_canvas, stretch=1)


        # 空白引導卡片
        self._empty_hint = QWidget()
        eh_layout = QVBoxLayout(self._empty_hint)
        eh_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        eh_layout.setSpacing(12)
        eh_layout.setContentsMargins(20, 40, 20, 40)

        lbl_hint_title = QLabel("此巨集尚無任何動作節點")
        lbl_hint_title.setStyleSheet(f"color: {COLORS['text_dim']}; font-size: 15px; font-weight: bold;")
        lbl_hint_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        eh_layout.addWidget(lbl_hint_title)

        lbl_hint_sub = QLabel("您可以直接從左側邊欄【拖曳動作模組/分支節點】至此，或點擊開始錄製：")
        lbl_hint_sub.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 12px;")
        lbl_hint_sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        eh_layout.addWidget(lbl_hint_sub)

        hint_btn_row = QHBoxLayout()
        hint_btn_row.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hint_btn_row.setSpacing(16)

        btn_hint_add = QPushButton("＋  手動新增動作")
        btn_hint_add.setStyleSheet("""
            QPushButton {
                background-color: #ea580c;
                color: #ffffff;
                font-weight: bold;
                font-size: 13px;
                border-radius: 4px;
            }
            QPushButton:hover { background-color: #f97316; }
        """)
        btn_hint_add.setFixedSize(160, 36)
        btn_hint_add.clicked.connect(self._show_add_menu)
        hint_btn_row.addWidget(btn_hint_add)

        btn_hint_record = QPushButton("⏺  自動捕捉錄製")
        btn_hint_record.setFixedSize(160, 36)
        btn_hint_record.setStyleSheet("background: #991b1b; color: white; font-weight: bold; border-radius: 4px;")
        btn_hint_record.clicked.connect(self._toggle_recording)
        hint_btn_row.addWidget(btn_hint_record)

        eh_layout.addLayout(hint_btn_row)
        cc_layout.addWidget(self._empty_hint)

        center_layout.addWidget(canvas_container, stretch=1)
        layout.addWidget(center_widget, stretch=1)

        self._refresh_empty_hint()

    # ── 公開介面 ──────────────────────────────────────────────
    def set_macro(self, macro: Optional[Macro]):
        self._macro = macro
        self._rebuild_list()

    def get_macro(self) -> Optional[Macro]:
        return self._macro

    def set_record_callback(self, cb: Callable):
        self._external_record_cb = cb

    def set_live_recording_state(self, is_recording: bool, hotkey_hint: str = ""):
        if is_recording:
            self._lbl_live_status.setText("🔴 錄製中")
            self._lbl_live_status.setStyleSheet("font-weight: bold; color: #ef4444; font-size: 13px;")
            self._lbl_live_action.setText(f"請在遊戲中操作... (按下 {hotkey_hint} 或點擊頂部停止)")
            self._lbl_live_action.setStyleSheet("color: #fca5a5; font-weight: bold;")
            self._live_monitor.setStyleSheet("""
                QFrame {
                    background: #2a1215;
                    border-bottom: 2px solid #ef4444;
                }
            """)
        else:
            self._lbl_live_status.setText("🟢 待機中")
            self._lbl_live_status.setStyleSheet("font-weight: bold; color: #4ade80; font-size: 12px;")
            self._lbl_live_action.setText("💡 提示：可從左側欄【拖曳動作模組/分支節點】至畫布；右鍵畫布可快速新增節點，選中按 [Delete] 刪除")
            self._lbl_live_action.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 12px;")
            self._live_monitor.setStyleSheet(f"""
                QFrame {{
                    background: {COLORS['bg_card']};
                    border-bottom: 1px solid {COLORS['border']};
                }}
            """)

    def update_live_action(self, action_text: str):
        self._lbl_live_action.setText(f"即時動作：{action_text}")
        self._lbl_live_action.setStyleSheet("color: #38bdf8; font-weight: bold; font-size: 13px;")

    def add_node_live(self, node: MacroNode):
        """即時將新錄製的節點加入當前巨集與橫向畫布"""
        if not self._macro:
            return
        if node not in self._macro.nodes:
            self._macro.nodes.append(node)
        self._aov_canvas.add_node_live(node)
        self._refresh_empty_hint()
        self._update_duration()

    def update_node_live(self, node: MacroNode):
        """即時更新節點屬性 (如按鍵放開時更新按住時間)"""
        if hasattr(self, "_aov_canvas"):
            self._aov_canvas.update_node_live(node)
        self._update_duration()

    def highlight_executing_node(self, index: int):
        """回放時高亮當前執行的圓圈節點"""
        self._aov_canvas.highlight_node(index)

    # ── 清單重建 ──────────────────────────────────────────────
    def _rebuild_list(self):
        if not self._macro:
            self._aov_canvas.set_nodes([])
            self._refresh_empty_hint()
            return
        self._aov_canvas.set_nodes(self._macro.nodes)
        self._refresh_empty_hint()
        self._update_duration()

    def _refresh_empty_hint(self):
        has_nodes = bool(self._macro and self._macro.nodes)
        self._empty_hint.setVisible(not has_nodes and bool(self._macro))
        self._aov_canvas.setVisible(has_nodes and bool(self._macro))

    def _update_duration(self):
        if self._macro:
            ms = self._macro.get_total_duration_ms()
            self._duration_label.setText(f"AOV 節點: {len(self._macro.nodes)}  |  估算: {ms} ms")

    # ── 節點操作 ──────────────────────────────────────────────
    def _show_add_menu(self):
        """顯示新增節點類型選單"""
        menu = QMenu(self)
        menu.setStyleSheet(f"""
            QMenu {{
                background: {COLORS['bg_card']};
                border: 1px solid {COLORS['border_accent']};
                border-radius: 6px;
                padding: 4px;
            }}
            QMenu::item {{
                padding: 6px 16px;
                border-radius: 3px;
            }}
            QMenu::item:selected {{
                background: {COLORS['bg_selected']};
                color: {COLORS['accent']};
            }}
            QMenu::separator {{
                height: 1px;
                background: {COLORS['border']};
                margin: 4px 8px;
            }}
        """)

        groups = [
            ("⌨️  鍵盤動作模組", [
                (NodeType.KEY_CLICK, "鍵盤按鍵點擊 (Click)"),
                (NodeType.KEY_DOWN,  "鍵盤按鍵按下 (Down/Hold)"),
                (NodeType.KEY_UP,    "鍵盤按鍵釋放 (Up/Release)"),
            ]),
            ("🖱️  滑鼠動作模組", [
                (NodeType.MOUSE_CLICK,  "滑鼠按鍵點擊 (Click)"),
                (NodeType.MOUSE_MOVE,   "滑鼠座標移動 (Move)"),
                (NodeType.MOUSE_SCROLL, "滑鼠滾輪滾動 (Scroll)"),
            ]),
            ("🎮  手把 / 搖桿動作", [
                (NodeType.GAMEPAD_BUTTON, "搖桿按鍵 (A, B, X, Y, LB, RB...)"),
                (NodeType.GAMEPAD_AXIS,   "搖桿軸推移 (蘑菇頭 LX/LY/RX/RY)"),
            ]),
            ("⏱️  時間等待與延遲", [
                (NodeType.WAIT_FIXED,  "固定時間延遲 (毫秒)"),
                (NodeType.WAIT_RANDOM, "隨機等待區間 (防偵測)"),
            ]),
            ("⏳  雙輸出分支邏輯", [
                (NodeType.COUNTER_BRANCH, "計時變數 X (雙輸出: 達X秒觸發 / 未觸發繼續)"),
                (NodeType.REPEAT_BLOCK,   "重複執行迴圈區塊"),
            ]),
        ]

        for title, items in groups:
            menu.addSection(title)
            for node_type, label in items:
                action = menu.addAction(f"  {label}")
                action.setData(node_type)
                action.triggered.connect(lambda checked, nt=node_type: self._add_node_by_type(nt))

        btn = self.sender()
        if btn and isinstance(btn, QWidget):
            pt = btn.mapToGlobal(QPoint(0, btn.height() + 2))
            menu.exec(pt)
        else:
            menu.exec(QtGui.QCursor.pos())

    def _add_node_by_type(self, node_type: str):
        self._add_node_at_pos(node_type, 0.0, 0.0)

    def _add_node_at_pos(self, node_type: str, x: float = 0.0, y: float = 0.0):
        """在指定座標處新增節點 (自動與前一節點水平打直對齊，間距加大至 220px 防止文字碰車)"""
        if not self._macro:
            return

        # 🎯 核心：精確計算與前級節點打直對齊的座標，確保位置永遠在所有節點的最尾端
        baseline_y = 150.0
        max_tail_x = 50.0

        if self._macro.nodes:
            baseline_y = getattr(self._macro.nodes[0], "pos_y", 150.0)
            if baseline_y <= 0:
                baseline_y = 150.0

            # 找出所有現有節點中 X 座標最大者，確保新節點永遠接在最尾端
            for n in self._macro.nodes:
                nx = getattr(n, "pos_x", 50.0)
                if nx > max_tail_x:
                    max_tail_x = nx
            target_x = max_tail_x + 220.0
        else:
            target_x = 50.0

        target_y = baseline_y

        nt_str = str(node_type)
        if "COUNTER_BRANCH" in nt_str:
            node = MacroNode(type=NodeType.COUNTER_BRANCH, var_name="X", timer_seconds=3.0)
            node.pos_x = target_x
            node.pos_y = target_y
            from ui.dialogs.counter_branch_dialog import CounterBranchDialog
            dlg = CounterBranchDialog(node, self._macro.nodes, self)
            if dlg.exec():
                new_node = dlg.get_node()
                new_node.pos_x = target_x
                new_node.pos_y = target_y
                self._macro.nodes.append(new_node)
                self._rebuild_list()
                self.macro_changed.emit()
            return

        # 其他節點類型 (鍵盤 / 滑鼠 / 手把 / 等待)
        node = MacroNode(type=node_type)
        node.pos_x = target_x
        node.pos_y = target_y
        from ui.dialogs.node_config_dialog import NodeConfigDialog
        dlg = NodeConfigDialog(node, self)
        dlg.setStyleSheet(self.styleSheet())
        if dlg.exec():
            new_node = dlg.get_node()
            new_node.pos_x = target_x
            new_node.pos_y = target_y
            self._macro.nodes.append(new_node)
            self._rebuild_list()
            self.macro_changed.emit()

    def _delete_node(self, node: MacroNode):
        if not self._macro:
            return
        self._macro.nodes = [n for n in self._macro.nodes if n.id != node.id]
        self._rebuild_list()
        self.macro_changed.emit()

    def _auto_layout_nodes(self):
        """一鍵自動整隊：去除重複節點、依序由左至右水平打直對齊 (間距 220px 箭頭打直、文字永不重疊)"""
        if not self._macro or not self._macro.nodes:
            return

        # 1. 依節點 ID 去重 (防止重複錄製造成的重複節點)
        seen_ids = set()
        unique_nodes = []
        for n in self._macro.nodes:
            if n.id not in seen_ids:
                seen_ids.add(n.id)
                unique_nodes.append(n)
        self._macro.nodes = unique_nodes

        # 2. 重新設定由左至右水平打直的座標 (間距 220px 杜絕文字重疊)
        start_x = 50.0
        start_y = 150.0
        spacing = 220.0

        for i, n in enumerate(self._macro.nodes):
            n.pos_x = start_x + i * spacing
            n.pos_y = start_y
            # 若不是分支節點且不是斷開(__END__)，將 next_node_id 設為 None，遵循列表依序順向單向連線
            if "COUNTER_BRANCH" not in str(n.type):
                if n.next_node_id != "__END__":
                    n.next_node_id = None

        self._rebuild_list()
        self.macro_changed.emit()

    def _copy_node(self, node: MacroNode):
        if not self._macro:
            return
        new_node = deepcopy(node)
        new_node.id = str(uuid.uuid4())
        try:
            idx = next(i for i, n in enumerate(self._macro.nodes) if n.id == node.id)
            self._macro.nodes.insert(idx + 1, new_node)
        except StopIteration:
            self._macro.nodes.append(new_node)
        self._rebuild_list()
        self.macro_changed.emit()

    def _edit_node(self, node: MacroNode):
        if "COUNTER_BRANCH" in str(node.type):
            from ui.dialogs.counter_branch_dialog import CounterBranchDialog
            dlg = CounterBranchDialog(node, self._macro.nodes, self)
            if dlg.exec():
                updated = dlg.get_node()
                for i, n in enumerate(self._macro.nodes):
                    if n.id == node.id:
                        self._macro.nodes[i] = updated
                        break
                self._rebuild_list()
                self.macro_changed.emit()
            return

        from ui.dialogs.node_config_dialog import NodeConfigDialog
        dlg = NodeConfigDialog(node, self)
        dlg.setStyleSheet(self.styleSheet())
        if dlg.exec():
            updated = dlg.get_node()
            for i, n in enumerate(self._macro.nodes):
                if n.id == node.id:
                    self._macro.nodes[i] = updated
                    break
            self._rebuild_list()
            self.macro_changed.emit()

    def _clear_all(self):
        if not self._macro or not self._macro.nodes:
            return
        reply = QMessageBox.question(
            self, "確認清空",
            f"確定要刪除所有 {len(self._macro.nodes)} 個節點嗎？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._macro.nodes.clear()
            self._rebuild_list()
            self.macro_changed.emit()

    # ── 錄製 ─────────────────────────────────────────────────
    def _toggle_recording(self):
        if hasattr(self, "_external_record_cb"):
            self._external_record_cb()
