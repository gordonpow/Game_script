"""
節點設定對話框
允許使用者設定每種 MacroNode 的屬性，並支援即時在「鍵盤 / 滑鼠 / 手把 / 等待 / 計時分支」之間自由切換
"""
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QLineEdit, QSpinBox, QDoubleSpinBox,
    QComboBox, QFrame, QCheckBox, QFormLayout, QWidget
)
from PyQt6.QtCore import Qt
from copy import deepcopy

from models.node import (
    MacroNode, NodeType, MouseButton, MouseClickType,
    ScrollDirection, GamepadButtonName, GamepadAxisName
)
from ui.theme import COLORS, NODE_ICONS


class NodeConfigDialog(QDialog):
    """節點屬性設定對話框（通用，支援切換動作類別）"""

    TYPE_OPTIONS = [
        ("⌨️  鍵盤按鍵點擊 (Key Click)",    NodeType.KEY_CLICK),
        ("⬇️  鍵盤按鍵按下 (Key Down)",     NodeType.KEY_DOWN),
        ("⬆️  鍵盤按鍵釋放 (Key Up)",       NodeType.KEY_UP),
        ("🖱️  滑鼠按鍵點擊 (Mouse Click)",  NodeType.MOUSE_CLICK),
        ("🎯  滑鼠座標移動 (Mouse Move)",   NodeType.MOUSE_MOVE),
        ("↕️  滑鼠滾輪滾動 (Mouse Scroll)", NodeType.MOUSE_SCROLL),
        ("🎮  手把搖桿按鍵 (Gamepad Btn)",   NodeType.GAMEPAD_BUTTON),
        ("🕹️  手把搖桿推桿 (Gamepad Axis)",  NodeType.GAMEPAD_AXIS),
        ("⏱️  固定時間等待 (Wait Fixed)",    NodeType.WAIT_FIXED),
        ("🎲  隨機時間等待 (Wait Random)",   NodeType.WAIT_RANDOM),
        ("⏳  計時變數 X (雙輸出分支)",      NodeType.COUNTER_BRANCH),
        ("↺   重複迴圈 (Repeat Block)",     NodeType.REPEAT_BLOCK),
    ]

    def __init__(self, node: MacroNode, parent=None):
        super().__init__(parent)
        self._node = deepcopy(node)  # 編輯副本
        self.setWindowTitle(f"設定節點  —  {NODE_ICONS.get(node.type, '')} {node.type}")
        self.setModal(True)
        self.setMinimumWidth(400)
        self._form_container = None
        self._form_layout = None
        self._setup_ui()

    def _setup_ui(self):
        self._main_layout = QVBoxLayout(self)
        self._main_layout.setSpacing(12)
        self._main_layout.setContentsMargins(18, 16, 18, 16)

        # ── 1. 頂部切換動作類別下拉選單 ─────────────────────
        type_box = QHBoxLayout()
        type_lbl = QLabel("動作類別：")
        type_lbl.setStyleSheet("font-weight: bold; color: #38bdf8; font-size: 13px;")
        type_box.addWidget(type_lbl)

        self._type_combo = QComboBox()
        self._type_combo.setStyleSheet("""
            QComboBox {
                background: #1e293b;
                color: #f8fafc;
                border: 1px solid #3b82f6;
                border-radius: 5px;
                padding: 5px 10px;
                font-weight: bold;
                font-size: 12px;
            }
            QComboBox::drop-down {
                border: none;
            }
            QComboBox QAbstractItemView {
                background: #1e293b;
                color: #f8fafc;
                selection-background-color: #2563eb;
            }
        """)
        for label, val in self.TYPE_OPTIONS:
            self._type_combo.addItem(label, val)

        # 找出當前節點對應的 index
        cur_t = self._node.type
        match_idx = -1
        for idx in range(self._type_combo.count()):
            if self._type_combo.itemData(idx) == cur_t or str(self._type_combo.itemData(idx)) in str(cur_t):
                match_idx = idx
                break
        if match_idx >= 0:
            self._type_combo.setCurrentIndex(match_idx)

        self._type_combo.currentIndexChanged.connect(self._on_type_changed)
        type_box.addWidget(self._type_combo, stretch=1)
        self._main_layout.addLayout(type_box)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"background: {COLORS['border']};")
        self._main_layout.addWidget(sep)

        # ── 2. 動態表單區域 ─────────────────────────────────
        self._form_container = QWidget()
        self._form_layout = QFormLayout(self._form_container)
        self._form_layout.setSpacing(10)
        self._form_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        self._main_layout.addWidget(self._form_container)

        self._build_fields(cur_t)

        # ── 3. 備註（通用） ─────────────────────────────────
        comm_box = QFormLayout()
        comm_box.setSpacing(10)
        comm_box.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        self._comment = QLineEdit(self._node.comment)
        self._comment.setPlaceholderText("選填，顯示在節點卡片下方")
        comm_box.addRow("節點備註：", self._comment)
        self._main_layout.addLayout(comm_box)

        self._main_layout.addStretch()

        # ── 4. 底部確定/取消按鈕 ─────────────────────────────
        btn_row = QHBoxLayout()
        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(self.reject)
        ok_btn = QPushButton("確認套用")
        ok_btn.setObjectName("btn_accent")
        ok_btn.clicked.connect(self._on_ok)
        btn_row.addStretch()
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(ok_btn)
        self._main_layout.addLayout(btn_row)

    def _on_type_changed(self, index: int):
        new_type = self._type_combo.itemData(index)
        self._build_fields(new_type)

    def _clear_form(self):
        while self._form_layout.count():
            item = self._form_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

    def _build_fields(self, t: NodeType | str):
        self._clear_form()
        t_str = str(t)

        if t in (NodeType.KEY_DOWN, NodeType.KEY_UP, NodeType.KEY_CLICK) or "KEY" in t_str:
            self._key_edit = QLineEdit(self._node.key or "a")
            self._key_edit.setPlaceholderText("如: w, a, s, d, space, f1, ctrl, enter")
            self._form_layout.addRow("鍵盤按鍵：", self._key_edit)

            if t == NodeType.KEY_CLICK or "CLICK" in t_str:
                self._hold_spin = QSpinBox()
                self._hold_spin.setRange(0, 10000)
                self._hold_spin.setSuffix(" ms")
                self._hold_spin.setValue(self._node.key_hold_ms or 50)
                self._form_layout.addRow("按住時長：", self._hold_spin)

        elif t in (NodeType.MOUSE_MOVE, NodeType.MOUSE_CLICK) or "MOUSE" in t_str:
            if t == NodeType.MOUSE_SCROLL or "SCROLL" in t_str:
                self._scroll_dir = QComboBox()
                for d in [ScrollDirection.UP, ScrollDirection.DOWN,
                          ScrollDirection.LEFT, ScrollDirection.RIGHT]:
                    self._scroll_dir.addItem(d.capitalize(), d)
                idx = self._scroll_dir.findData(self._node.scroll_direction)
                if idx >= 0:
                    self._scroll_dir.setCurrentIndex(idx)
                self._form_layout.addRow("滾輪方向：", self._scroll_dir)

                self._scroll_amount = QSpinBox()
                self._scroll_amount.setRange(1, 50)
                self._scroll_amount.setValue(self._node.scroll_amount or 3)
                self._form_layout.addRow("滾動格數：", self._scroll_amount)
            else:
                self._rel_x = QDoubleSpinBox()
                self._rel_x.setRange(0.0, 1.0)
                self._rel_x.setDecimals(4)
                self._rel_x.setSingleStep(0.01)
                self._rel_x.setValue(self._node.rel_x)
                self._form_layout.addRow("目標 X 比例 (0~1)：", self._rel_x)

                self._rel_y = QDoubleSpinBox()
                self._rel_y.setRange(0.0, 1.0)
                self._rel_y.setDecimals(4)
                self._rel_y.setSingleStep(0.01)
                self._rel_y.setValue(self._node.rel_y)
                self._form_layout.addRow("目標 Y 比例 (0~1)：", self._rel_y)

                if t == NodeType.MOUSE_MOVE or "MOVE" in t_str:
                    self._move_dur = QSpinBox()
                    self._move_dur.setRange(0, 10000)
                    self._move_dur.setSuffix(" ms")
                    self._move_dur.setValue(self._node.move_duration_ms or 100)
                    self._form_layout.addRow("移動時長：", self._move_dur)

                elif t == NodeType.MOUSE_CLICK or "CLICK" in t_str:
                    self._btn_combo = QComboBox()
                    for b in [MouseButton.LEFT, MouseButton.RIGHT, MouseButton.MIDDLE]:
                        self._btn_combo.addItem(b.capitalize(), b)
                    idx = self._btn_combo.findData(self._node.button)
                    if idx >= 0:
                        self._btn_combo.setCurrentIndex(idx)
                    self._form_layout.addRow("滑鼠按鍵：", self._btn_combo)

                    self._click_combo = QComboBox()
                    click_options = [
                        ("單擊 (Single Click)", MouseClickType.SINGLE),
                        ("雙擊 (Double Click)", MouseClickType.DOUBLE),
                        ("按下 (Down/Hold)",   MouseClickType.DOWN),
                        ("釋放 (Up/Release)",  MouseClickType.UP),
                    ]
                    for label, val in click_options:
                        self._click_combo.addItem(label, val)
                    idx = self._click_combo.findData(self._node.click_type)
                    if idx >= 0:
                        self._click_combo.setCurrentIndex(idx)
                    self._form_layout.addRow("點擊模式：", self._click_combo)

        elif t == NodeType.WAIT_FIXED or t == "WAIT_FIXED":
            self._dur_spin = QSpinBox()
            self._dur_spin.setRange(0, 999999)
            self._dur_spin.setSuffix(" ms")
            self._dur_spin.setValue(self._node.duration_ms or 500)
            self._form_layout.addRow("等待時長：", self._dur_spin)

        elif t == NodeType.WAIT_RANDOM or t == "WAIT_RANDOM":
            self._min_spin = QSpinBox()
            self._min_spin.setRange(0, 999999)
            self._min_spin.setSuffix(" ms")
            self._min_spin.setValue(self._node.min_ms or 200)
            self._form_layout.addRow("最短等待：", self._min_spin)

            self._max_spin = QSpinBox()
            self._max_spin.setRange(0, 999999)
            self._max_spin.setSuffix(" ms")
            self._max_spin.setValue(self._node.max_ms or 600)
            self._form_layout.addRow("最長等待：", self._max_spin)

        elif t == NodeType.GAMEPAD_BUTTON or "GAMEPAD_BUTTON" in t_str:
            self._gp_btn = QComboBox()
            for b in GamepadButtonName:
                self._gp_btn.addItem(b.value, b.value)
            idx = self._gp_btn.findData(getattr(self._node, "gamepad_button", GamepadButtonName.A) or GamepadButtonName.A)
            if idx >= 0:
                self._gp_btn.setCurrentIndex(idx)
            self._form_layout.addRow("手把按鍵：", self._gp_btn)

            self._gp_action = QComboBox()
            for a, label in [("click", "點擊 (Click)"), ("down", "按下 (Hold)"), ("up", "釋放 (Release)")]:
                self._gp_action.addItem(label, a)
            idx = self._gp_action.findData(getattr(self._node, "gamepad_action", "click") or "click")
            if idx >= 0:
                self._gp_action.setCurrentIndex(idx)
            self._form_layout.addRow("手把動作：", self._gp_action)

        elif t == NodeType.GAMEPAD_AXIS or "GAMEPAD_AXIS" in t_str:
            self._gp_axis = QComboBox()
            for ax in GamepadAxisName:
                self._gp_axis.addItem(ax.value, ax.value)
            idx = self._gp_axis.findData(getattr(self._node, "gamepad_axis", GamepadAxisName.LX) or GamepadAxisName.LX)
            if idx >= 0:
                self._gp_axis.setCurrentIndex(idx)
            self._form_layout.addRow("搖桿軸向：", self._gp_axis)

            self._axis_val = QDoubleSpinBox()
            self._axis_val.setRange(-1.0, 1.0)
            self._axis_val.setDecimals(2)
            self._axis_val.setSingleStep(0.1)
            self._axis_val.setValue(getattr(self._node, "axis_value", 1.0))
            self._form_layout.addRow("推桿幅度 (-1~1)：", self._axis_val)

            self._axis_dur = QSpinBox()
            self._axis_dur.setRange(0, 10000)
            self._axis_dur.setSuffix(" ms")
            self._axis_dur.setValue(getattr(self._node, "axis_duration_ms", 100) or 100)
            self._form_layout.addRow("持續推動時長：", self._axis_dur)

        elif t == NodeType.REPEAT_BLOCK or "REPEAT" in t_str:
            self._repeat_cnt = QSpinBox()
            self._repeat_cnt.setRange(1, 99999)
            self._repeat_cnt.setValue(self._node.repeat_count or 1)
            self._form_layout.addRow("重複次數：", self._repeat_cnt)

        elif "COUNTER_BRANCH" in t_str:
            self._branch_var = QLineEdit(getattr(self._node, "var_name", "X") or "X")
            self._branch_var.setPlaceholderText("例如: X, timer_1, skill_cd")
            self._form_layout.addRow("計時變數名稱：", self._branch_var)

            self._branch_sec = QDoubleSpinBox()
            self._branch_sec.setRange(0.1, 999.0)
            self._branch_sec.setSingleStep(0.5)
            self._branch_sec.setDecimals(1)
            self._branch_sec.setSuffix(" 秒")
            self._branch_sec.setValue(float(getattr(self._node, "timer_seconds", 3.0)))
            self._form_layout.addRow("目標計時 X：", self._branch_sec)

            self._branch_trig = QComboBox()
            self._branch_trig.addItem("⏳ 時間達到 X 秒 (timeout)", "timeout")
            self._branch_trig.addItem("⌨ 按鍵放開時觸發 (key_release)", "key_release")
            idx = self._branch_trig.findData(getattr(self._node, "trigger_type", "timeout"))
            if idx >= 0:
                self._branch_trig.setCurrentIndex(idx)
            self._form_layout.addRow("觸發條件：", self._branch_trig)

    def _on_ok(self):
        """將表單值寫回節點"""
        chosen_type = self._type_combo.currentData()
        self._node.type = chosen_type
        t = chosen_type
        t_str = str(t)

        if t in (NodeType.KEY_DOWN, NodeType.KEY_UP, NodeType.KEY_CLICK) or "KEY" in t_str:
            if hasattr(self, "_key_edit"):
                self._node.key = self._key_edit.text().strip().lower()
            if hasattr(self, "_hold_spin"):
                self._node.key_hold_ms = self._hold_spin.value()

        elif t in (NodeType.MOUSE_MOVE, NodeType.MOUSE_CLICK) or "MOUSE" in t_str:
            if t == NodeType.MOUSE_SCROLL or "SCROLL" in t_str:
                if hasattr(self, "_scroll_dir"):
                    self._node.scroll_direction = self._scroll_dir.currentData()
                if hasattr(self, "_scroll_amount"):
                    self._node.scroll_amount = self._scroll_amount.value()
            else:
                if hasattr(self, "_rel_x"):
                    self._node.rel_x = self._rel_x.value()
                if hasattr(self, "_rel_y"):
                    self._node.rel_y = self._rel_y.value()
                if hasattr(self, "_move_dur"):
                    self._node.move_duration_ms = self._move_dur.value()
                if hasattr(self, "_btn_combo"):
                    self._node.button = self._btn_combo.currentData()
                if hasattr(self, "_click_combo"):
                    self._node.click_type = self._click_combo.currentData()

        elif t == NodeType.WAIT_FIXED:
            if hasattr(self, "_dur_spin"):
                self._node.duration_ms = self._dur_spin.value()

        elif t == NodeType.WAIT_RANDOM:
            if hasattr(self, "_min_spin"):
                self._node.min_ms = self._min_spin.value()
            if hasattr(self, "_max_spin"):
                self._node.max_ms = max(self._max_spin.value(), self._node.min_ms)

        elif t == NodeType.GAMEPAD_BUTTON:
            if hasattr(self, "_gp_btn"):
                self._node.gamepad_button = self._gp_btn.currentData()
            if hasattr(self, "_gp_action"):
                self._node.gamepad_action = self._gp_action.currentData()

        elif t == NodeType.GAMEPAD_AXIS:
            if hasattr(self, "_gp_axis"):
                self._node.gamepad_axis = self._gp_axis.currentData()
            if hasattr(self, "_axis_val"):
                self._node.axis_value = self._axis_val.value()
            if hasattr(self, "_axis_dur"):
                self._node.axis_duration_ms = self._axis_dur.value()
                self._node.duration_ms = self._axis_dur.value()

        elif t == NodeType.REPEAT_BLOCK:
            if hasattr(self, "_repeat_cnt"):
                self._node.repeat_count = self._repeat_cnt.value()

        elif "COUNTER_BRANCH" in t_str:
            if hasattr(self, "_branch_var"):
                self._node.var_name = self._branch_var.text().strip() or "X"
            if hasattr(self, "_branch_sec"):
                self._node.timer_seconds = self._branch_sec.value()
            if hasattr(self, "_branch_trig"):
                self._node.trigger_type = self._branch_trig.currentData()

        self._node.comment = self._comment.text().strip()
        self.accept()

    def get_node(self) -> MacroNode:
        return self._node
