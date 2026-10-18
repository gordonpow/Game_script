"""
橫向 AOV 節點圖形畫布 (AOV Node Graph Canvas)
- 深色高對比窗格/網格背景 (Grid Pattern)，支援 25px 自動吸附對齊
- 節點可自由拖曳移動 (Free Draggable Nodes with Grid Snapping)
- 滑鼠在輸出端點 (Port) 上拖曳直接拉出箭頭連線
- 後級節點輸入端具有【自動磁吸功能 (Magnetic Snapping)】：
  拖曳接近目標輸入孔半徑 45px 時，自動吸附對齊並發出綠色吸附光環，放開即完成連線！
- 支援右鍵選單直接切換連線目標、Delete 鍵刪除、雙擊編輯屬性
"""
from __future__ import annotations
from typing import Optional, List, Dict, Tuple
from copy import deepcopy
import uuid
import math

from ui.qt_compat import (
    QtWidgets, QtCore, QtGui, Qt
)
from PyQt6.QtWidgets import (
    QWidget, QScrollArea, QMenu, QMessageBox
)
from PyQt6.QtCore import Qt, pyqtSignal, QPoint, QPointF, QRect, QSize
from PyQt6.QtGui import (
    QPainter, QColor, QPen, QBrush, QFont, QPolygon,
    QPainterPath, QWheelEvent, QKeyEvent, QDragEnterEvent, QDropEvent
)

from models.node import MacroNode, NodeType
from ui.theme import COLORS, NODE_ICONS

GRID_SIZE = 25  # 窗格網格步長
PORT_RADIUS = 5 # 端口半徑


class HorizontalAovNodeItem(QWidget):
    """
    自由拖曳節點 Widget (可吸附至網格窗格)
    支援鼠標在輸出端點上按住拖曳直接拉箭頭，並支援後級輸入端磁吸
    """
    selected = pyqtSignal(object)           # 傳 self
    delete_requested = pyqtSignal(object)   # 傳 node
    copy_requested = pyqtSignal(object)     # 傳 node
    edit_requested = pyqtSignal(object)     # 傳 node
    node_moved = pyqtSignal(object)         # 傳 node (更新座標)
    connection_changed = pyqtSignal(object) # 傳 node (更新連線目標)

    def __init__(
        self,
        node: MacroNode,
        index: int = 0,
        total: int = 1,
        all_nodes: Optional[List[MacroNode]] = None,
        parent=None
    ):
        super().__init__(parent)
        self._node = node
        self._index = index
        self._total = total
        self._all_nodes = all_nodes or []
        self._is_selected = False
        self._is_executing = False

        # 拖曳節點狀態
        self._is_dragging = False
        self._drag_start_pos = QPoint()
        self._drag_node_pos = QPoint()

        # 拉線狀態
        self._is_wiring = False
        self._wiring_port = ""  # "normal", "trigger", "continue"
        self._hovered_port = ""

        # 磁吸高亮狀態
        self._is_input_snapped = False

        self.setFixedWidth(144)
        self.setFixedHeight(135)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setMouseTracking(True)  # 啟用懸停檢測

    @property
    def node(self) -> MacroNode:
        return self._node

    @property
    def index(self) -> int:
        return self._index

    def set_index(self, index: int, total: int, all_nodes: Optional[List[MacroNode]] = None):
        self._index = index
        self._total = total
        if all_nodes is not None:
            self._all_nodes = all_nodes
        self.update()

    def set_selected(self, selected: bool):
        self._is_selected = selected
        self.update()

    def set_executing(self, executing: bool):
        self._is_executing = executing
        self.update()

    def set_input_snapped(self, snapped: bool):
        """磁吸狀態更新 (若被連線接近則高亮吸附)"""
        if self._is_input_snapped != snapped:
            self._is_input_snapped = snapped
            self.update()

    def update_zoom(self, zoom: float):
        """根據縮放比例更新節點在畫布上的物理座標"""
        self._zoom = zoom
        nx = int(self._node.pos_x * zoom)
        ny = int(self._node.pos_y * zoom)
        self.move(nx, ny)
        self.update()

    # ── 端口絕對座標定義 (向內縮排 14px 確保為 100% 完整無裁切圓形) ──
    def get_input_port_pos(self) -> QPoint:
        """取得輸入端點在畫布上的絕對座標"""
        if "COUNTER_BRANCH" in str(self._node.type):
            cx = self.width() // 2
            cy = 58
            d_size = 28
            return QPoint(self.x() + cx - d_size, self.y() + cy)
        return QPoint(self.x() + 14, self.y() + 58)

    def get_output_port_pos(self) -> QPoint:
        """取得普通輸出端點絕對座標"""
        return QPoint(self.x() + self.width() - 14, self.y() + 58)

    def get_trigger_port_pos(self) -> QPoint:
        """取得分支【If/觸發】右頂點輸出端點絕對座標"""
        if "COUNTER_BRANCH" in str(self._node.type):
            cx = self.width() // 2
            cy = 58
            d_size = 28
            return QPoint(self.x() + cx + d_size, self.y() + cy)
        return QPoint(self.x() + self.width() - 14, self.y() + 46)

    def get_continue_port_pos(self) -> QPoint:
        """取得分支【Else/繼續】上頂點輸出端點絕對座標 (如圖 1 頂部 else 出口)"""
        if "COUNTER_BRANCH" in str(self._node.type):
            cx = self.width() // 2
            cy = 58
            d_size = 28
            return QPoint(self.x() + cx, self.y() + cy - d_size)
        return QPoint(self.x() + self.width() - 14, self.y() + 70)

    # ── 檢測滑鼠是否落在輸出端口圓點上 ─────────────────────────
    def _hit_output_port(self, pos: QPoint) -> Optional[str]:
        """檢測滑鼠在節點內部座標是否位於某個輸出端口 (半徑 20px 友善感應範圍)"""
        w = self.width()
        is_branch = ("COUNTER_BRANCH" in str(self._node.type))

        if not is_branch:
            pt = QPoint(w - 14, 58)
            dx = pos.x() - pt.x()
            dy = pos.y() - pt.y()
            if (dx * dx + dy * dy) <= (20 * 20):
                return "normal"
        else:
            cx = w // 2
            cy = 58
            d_size = 28
            pt_trig = QPoint(cx + d_size, cy)      # 右頂點 (if / 觸發)
            pt_cont = QPoint(cx, cy - d_size)      # 上頂點 (else / 繼續)
            dx1, dy1 = pos.x() - pt_trig.x(), pos.y() - pt_trig.y()
            if (dx1 * dx1 + dy1 * dy1) <= (20 * 20):
                return "trigger"
            dx2, dy2 = pos.x() - pt_cont.x(), pos.y() - pt_cont.y()
            if (dx2 * dx2 + dy2 * dy2) <= (20 * 20):
                return "continue"
        return None

    # ── 檢測滑鼠是否落在輸入端口圓點上 ─────────────────────────
    def _hit_input_port(self, pos: QPoint) -> bool:
        """檢測滑鼠在節點內部座標是否位於輸入端口 (半徑 20px 感應範圍)"""
        if "COUNTER_BRANCH" in str(self._node.type):
            cx = self.width() // 2
            cy = 58
            d_size = 28
            pt = QPoint(cx - d_size, cy)
        else:
            pt = QPoint(14, 58)
        dx = pos.x() - pt.x()
        dy = pos.y() - pt.y()
        return (dx * dx + dy * dy) <= (20 * 20)

    # ── 斷開所有連向本節點的輸入連線 ───────────────────────────
    def _disconnect_incoming_connections(self):
        """斷開所有連向本節點的連線"""
        graph_area = self.parent()
        if not graph_area:
            return
        canvas = getattr(graph_area, "_canvas", None)
        items: List[HorizontalAovNodeItem] = getattr(canvas, "_items", []) if canvas else []
        disconnected_any = False

        for it in items:
            n = it.node
            # 普通連線指向本節點
            if n.next_node_id == self._node.id:
                n.next_node_id = "__END__"
                it.connection_changed.emit(n)
                disconnected_any = True
            # 分支觸發指向本節點
            if n.on_trigger_target_id == self._node.id:
                n.on_trigger_target_id = None
                it.connection_changed.emit(n)
                disconnected_any = True
            # 分支繼續指向本節點
            if n.on_continue_target_id == self._node.id:
                n.on_continue_target_id = None
                it.connection_changed.emit(n)
                disconnected_any = True

        # 若是預設循序連線的前一個節點且 next_node_id 為 None
        for idx, it in enumerate(items):
            if idx + 1 < len(items) and items[idx + 1] == self:
                if it.node.next_node_id is None:
                    it.node.next_node_id = "__END__"
                    it.connection_changed.emit(it.node)
                    disconnected_any = True

        if disconnected_any:
            graph_area.update()

    # ── 滑鼠互動：拖曳節點 vs 點擊端口拉線 vs 拖曳輸入孔斷開 ─────
    def mousePressEvent(self, event):
        # 1. 中鍵按下 ➔ 轉發給畫布啟動平移 (Pan)
        if event.button() == Qt.MouseButton.MiddleButton:
            graph_area = self.parent()
            if graph_area and hasattr(graph_area, "mousePressEvent"):
                graph_area.mousePressEvent(event)
            event.accept()
            return

        if event.button() == Qt.MouseButton.LeftButton:
            # 2. 點擊輸入小圓點 ➔ 準備拖曳斷開連線
            if self._hit_input_port(event.pos()):
                self._is_disconnecting_input = True
                self._disconnect_start_pos = event.pos()
                event.accept()
                return

            # 3. 點擊輸出小圓點 ➔ 啟動直接拉箭頭連線！
            port = self._hit_output_port(event.pos())
            if port:
                self._is_wiring = True
                self._wiring_port = port
                graph_area = self.parent()
                if graph_area and hasattr(graph_area, "start_wiring"):
                    graph_area.start_wiring(self, port)
                event.accept()
                return
            else:
                # 4. 點擊節點本體 ➔ 拖曳移動節點
                self._is_dragging = True
                self._drag_start_pos = event.globalPosition().toPoint()
                self._drag_node_pos = self.pos()
                self.selected.emit(self)
                self.raise_()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        # 中鍵拖曳 ➔ 平移
        if event.buttons() & Qt.MouseButton.MiddleButton:
            graph_area = self.parent()
            if graph_area and hasattr(graph_area, "mouseMoveEvent"):
                graph_area.mouseMoveEvent(event)
            event.accept()
            return

        if getattr(self, "_is_disconnecting_input", False):
            # 拖曳輸入孔超過 12px ➔ 斷開連線！
            diff = event.pos() - getattr(self, "_disconnect_start_pos", event.pos())
            if diff.manhattanLength() > 12:
                self._is_disconnecting_input = False
                self._disconnect_incoming_connections()
                self.setCursor(Qt.CursorShape.PointingHandCursor)
                self.setToolTip("已斷開連入此節點的箭頭連線")
            event.accept()
            return

        if self._is_wiring:
            # 正在拉箭頭連線：將滑鼠位置轉移給父畫布進行磁吸計算
            graph_area = self.parent()
            if graph_area and hasattr(graph_area, "update_wiring"):
                local_pt = graph_area.mapFromGlobal(event.globalPosition().toPoint())
                graph_area.update_wiring(local_pt)
            event.accept()
            return
        elif self._is_dragging:
            # 正在移動節點
            delta = event.globalPosition().toPoint() - self._drag_start_pos
            new_pos = self._drag_node_pos + delta
            nx = max(GRID_SIZE, new_pos.x())
            ny = max(GRID_SIZE, new_pos.y())
            self.move(nx, ny)
            if self.parent():
                self.parent().update()  # 即時重繪所有連接箭頭
        else:
            # 懸停檢測
            if self._hit_input_port(event.pos()):
                self.setCursor(Qt.CursorShape.PointingHandCursor)
                self.setToolTip("按住向外拖曳：斷開連入此節點的箭頭連線")
            else:
                port = self._hit_output_port(event.pos())
                if port != self._hovered_port:
                    self._hovered_port = port or ""
                    self.update()
                if port:
                    self.setCursor(Qt.CursorShape.CrossCursor)
                    self.setToolTip("按住拖曳：拉出箭頭連線至目標節點")
                else:
                    self.setCursor(Qt.CursorShape.PointingHandCursor)
                    self.setToolTip("")
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.MiddleButton:
            graph_area = self.parent()
            if graph_area and hasattr(graph_area, "mouseReleaseEvent"):
                graph_area.mouseReleaseEvent(event)
            event.accept()
            return

        self._is_disconnecting_input = False

        if self._is_wiring:
            self._is_wiring = False
            self._wiring_port = ""
            graph_area = self.parent()
            if graph_area and hasattr(graph_area, "finish_wiring"):
                graph_area.finish_wiring()
            event.accept()
            return
        elif self._is_dragging:
            self._is_dragging = False
            # 自動吸附網格 (Snap to Grid)
            snap_x = round(self.x() / GRID_SIZE) * GRID_SIZE
            snap_y = round(self.y() / GRID_SIZE) * GRID_SIZE
            snap_x = max(50, snap_x)
            snap_y = max(50, snap_y)

            # 🎯 智慧水平磁吸：若與其他任何節點的高度相差在 35px 內，自動強磁吸對齊至同一水平 Y 軸！
            aligned_y = None
            min_dy = 9999
            for it in self._all_nodes:
                if it.id != self._node.id and getattr(it, "pos_y", 0) > 0:
                    dy = abs(snap_y - it.pos_y)
                    if dy < min_dy and dy <= 35:
                        min_dy = dy
                        aligned_y = it.pos_y
            if aligned_y is not None:
                snap_y = int(aligned_y)

            self.move(snap_x, snap_y)

            # 存入節點物件
            self._node.pos_x = float(snap_x)
            self._node.pos_y = float(snap_y)
            self.node_moved.emit(self._node)

            if self.parent():
                self.parent().update()
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.edit_requested.emit(self._node)
        super().mouseDoubleClickEvent(event)

    def contextMenuEvent(self, event):
        """滑鼠右鍵選單：更改鍵位、自訂箭頭連線去哪裡、複製、刪除"""
        self.selected.emit(self)
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: #1e293b;
                color: #f8fafc;
                border: 1px solid #3b82f6;
                border-radius: 6px;
                padding: 4px;
                font-size: 13px;
                font-family: Consolas, monospace;
            }
            QMenu::item {
                padding: 7px 22px 7px 14px;
                border-radius: 4px;
            }
            QMenu::item:selected {
                background-color: #2563eb;
                color: #ffffff;
            }
            QMenu::separator {
                height: 1px;
                background-color: #334155;
                margin: 4px 6px;
            }
        """)

        t_str = str(self._node.type)
        is_branch = ("COUNTER_BRANCH" in t_str)

        # 1. 編輯動作與模式切換
        if is_branch:
            act_edit = menu.addAction("⚙️  設定判斷條件與屬性 (Scratch 設定介面)...")
            act_edit.triggered.connect(lambda: self.edit_requested.emit(self._node))

            menu.addSeparator()

            curr_mode = getattr(self._node, "branch_mode", "timer")
            act_mode_timer = menu.addAction("⏱️  切換模式 ➔ 計時器模式 (Timer Mode)")
            act_mode_timer.setCheckable(True)
            act_mode_timer.setChecked(curr_mode == "timer")
            act_mode_timer.triggered.connect(lambda: self._set_branch_mode("timer"))

            act_mode_comp = menu.addAction("🔢  切換模式 ➔ 區域變數比較大小 (Scratch > < =)")
            act_mode_comp.setCheckable(True)
            act_mode_comp.setChecked(curr_mode == "compare")
            act_mode_comp.triggered.connect(lambda: self._set_branch_mode("compare"))
        else:
            act_edit = menu.addAction("✏  更改鍵位 / 編輯屬性")
            act_edit.triggered.connect(lambda: self.edit_requested.emit(self._node))

        menu.addSeparator()

        # 2. 🔗 自訂箭頭連線去哪裡 (亦可直接點右側/上側小圓點拖曳)
        letters = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"

        if not is_branch:
            curr_target = self._node.next_node_id
            menu_target = menu.addMenu("🔗  調整箭頭連線至 (或拖曳右側小圓點)...")
            
            act_def = menu_target.addAction("🔁 自動依序連線 (預設下一節點)")
            act_def.setCheckable(True)
            act_def.setChecked(curr_target is None)
            act_def.triggered.connect(lambda: self._set_next_target(None))

            act_end = menu_target.addAction("⏹ 結束腳本 (不連線/直接結束)")
            act_end.setCheckable(True)
            act_end.setChecked(curr_target == "__END__")
            act_end.triggered.connect(lambda: self._set_next_target("__END__"))

            menu_target.addSeparator()

            for idx, target_n in enumerate(self._all_nodes):
                if target_n.id == self._node.id:
                    continue
                lbl_tag = letters[idx] if idx < len(letters) else f"{idx+1}"
                act_item = menu_target.addAction(f"➔ 節點 [{lbl_tag}] : {target_n.get_display_name()[:16]}")
                act_item.setCheckable(True)
                act_item.setChecked(curr_target == target_n.id)
                act_item.triggered.connect(lambda checked, tid=target_n.id: self._set_next_target(tid))

        else:
            menu_trig = menu.addMenu("⚡  調整【If 成立分支】連線至 (右側頂點)...")
            act_trig_none = menu_trig.addAction("❌ 未指定目標 (僅執行分支內部動作)")
            act_trig_none.setCheckable(True)
            act_trig_none.setChecked(self._node.on_trigger_target_id is None)
            act_trig_none.triggered.connect(lambda: self._set_trigger_target(None))
            menu_trig.addSeparator()

            for idx, target_n in enumerate(self._all_nodes):
                if target_n.id == self._node.id:
                    continue
                lbl_tag = letters[idx] if idx < len(letters) else f"{idx+1}"
                act_item = menu_trig.addAction(f"⚡ 節點 [{lbl_tag}] : {target_n.get_display_name()[:16]}")
                act_item.setCheckable(True)
                act_item.setChecked(self._node.on_trigger_target_id == target_n.id)
                act_item.triggered.connect(lambda checked, tid=target_n.id: self._set_trigger_target(tid))

            menu_cont = menu.addMenu("↪  調整【Else 分支】連線至 (圖1上頂點)...")
            act_cont_def = menu_cont.addAction("🔁 自動依序連線 (預設下一節點)")
            act_cont_def.setCheckable(True)
            act_cont_def.setChecked(self._node.on_continue_target_id is None)
            act_cont_def.triggered.connect(lambda: self._set_continue_target(None))
            menu_cont.addSeparator()

            for idx, target_n in enumerate(self._all_nodes):
                if target_n.id == self._node.id:
                    continue
                lbl_tag = letters[idx] if idx < len(letters) else f"{idx+1}"
                act_item = menu_cont.addAction(f"▶ 節點 [{lbl_tag}] : {target_n.get_display_name()[:16]}")
                act_item.setCheckable(True)
                act_item.setChecked(self._node.on_continue_target_id == target_n.id)
                act_item.triggered.connect(lambda checked, tid=target_n.id: self._set_continue_target(tid))

        menu.addSeparator()

        # 3. 🔄 切換動作類型 (快速轉換為 鍵盤 / 滑鼠 / 手把 / 等待 / 計時分支)
        menu_convert = menu.addMenu("🔄  切換動作模式 (鍵盤 / 手把 / 滑鼠)...")
        act_c_key = menu_convert.addAction("⌨️ 切換為 鍵盤按鍵 (Key Click)")
        act_c_key.triggered.connect(lambda: self._convert_to_type(NodeType.KEY_CLICK))
        act_c_mouse = menu_convert.addAction("🖱️ 切換為 滑鼠點擊 (Mouse Click)")
        act_c_mouse.triggered.connect(lambda: self._convert_to_type(NodeType.MOUSE_CLICK))
        act_c_pad = menu_convert.addAction("🎮 切換為 手把按鈕 (Gamepad Button)")
        act_c_pad.triggered.connect(lambda: self._convert_to_type(NodeType.GAMEPAD_BUTTON))
        act_c_axis = menu_convert.addAction("🕹️ 切換為 搖桿推桿 (Gamepad Axis)")
        act_c_axis.triggered.connect(lambda: self._convert_to_type(NodeType.GAMEPAD_AXIS))
        act_c_wait = menu_convert.addAction("⏱️ 切換為 時間延時 (Wait Fixed)")
        act_c_wait.triggered.connect(lambda: self._convert_to_type(NodeType.WAIT_FIXED))
        act_c_branch = menu_convert.addAction("⏳ 切換為 計時分支 (Counter Branch)")
        act_c_branch.triggered.connect(lambda: self._convert_to_type(NodeType.COUNTER_BRANCH))

        # 4. ➕ 在此節點後新增動作
        menu_insert = menu.addMenu("➕  在此節點後新增動作...")
        act_i_key = menu_insert.addAction("⌨️ 鍵盤按鍵動作")
        act_i_key.triggered.connect(lambda: self._insert_after_type(NodeType.KEY_CLICK))
        act_i_mouse = menu_insert.addAction("🖱️ 滑鼠操作動作")
        act_i_mouse.triggered.connect(lambda: self._insert_after_type(NodeType.MOUSE_CLICK))
        act_i_pad = menu_insert.addAction("🎮 手把搖桿動作")
        act_i_pad.triggered.connect(lambda: self._insert_after_type(NodeType.GAMEPAD_BUTTON))
        act_i_wait = menu_insert.addAction("⏱️ 時間等待延時")
        act_i_wait.triggered.connect(lambda: self._insert_after_type(NodeType.WAIT_FIXED))
        act_i_branch = menu_insert.addAction("⏳ 計時雙輸出分支")
        act_i_branch.triggered.connect(lambda: self._insert_after_type(NodeType.COUNTER_BRANCH))

        # 5. 水平打直對齊 (一鍵對齊至水平基準線)
        act_align = menu.addAction("🪄  水平打直對齊 (對齊至同行節點)")
        act_align.triggered.connect(self._align_to_horizontal_baseline)

        menu.addSeparator()

        # 6. 複製動作節點
        act_copy = menu.addAction("⧉  複製動作節點 (Ctrl+C)")
        act_copy.triggered.connect(lambda: self.copy_requested.emit(self._node))

        menu.addSeparator()

        # 7. 刪除
        act_del = menu.addAction("🗑️  刪除此節點 (Delete)")
        act_del.triggered.connect(lambda: self.delete_requested.emit(self._node))

        menu.exec(event.globalPos())

    def _align_to_horizontal_baseline(self):
        """將此節點水平對齊至同行其他節點的水平線 (預設 150.0)"""
        target_y = 150.0
        for n in self._all_nodes:
            if n.id != self._node.id and getattr(n, "pos_y", 0) > 0:
                target_y = n.pos_y
                break
        self._node.pos_y = target_y
        self.move(int(self._node.pos_x * getattr(self, "_zoom", 1.0)), int(target_y * getattr(self, "_zoom", 1.0)))
        self.node_moved.emit(self._node)
        if self.parent():
            self.parent().update()

    def _convert_to_type(self, target_type: NodeType):
        """將目前節點切換為指定類型"""
        self._node.type = target_type
        if target_type in (NodeType.KEY_CLICK, NodeType.KEY_DOWN, NodeType.KEY_UP):
            if not self._node.key:
                self._node.key = "a"
        elif target_type == NodeType.GAMEPAD_BUTTON:
            if not getattr(self._node, "gamepad_button", None):
                self._node.gamepad_button = GamepadButtonName.A
        elif target_type == NodeType.MOUSE_CLICK:
            if not getattr(self._node, "button", None):
                self._node.button = MouseButton.LEFT
        elif target_type == NodeType.WAIT_FIXED:
            if not getattr(self._node, "duration_ms", None):
                self._node.duration_ms = 500
        elif target_type == NodeType.COUNTER_BRANCH:
            self._node.var_name = "X"
            self._node.timer_seconds = 3.0
            self._node.trigger_type = "timeout"
        self.edit_requested.emit(self._node)

    def _insert_after_type(self, node_type: NodeType):
        """在此節點右側新增動作節點"""
        graph_area = self.parent()
        if graph_area and hasattr(graph_area, "_canvas") and graph_area._canvas:
            x = self.x() + 175
            y = self.y()
            zoom = getattr(graph_area._canvas, "_zoom_factor", 1.0)
            graph_area._canvas.add_node_at_pos_requested.emit(node_type, x / zoom, y / zoom)

    def _set_branch_mode(self, mode: str):
        """切換分支模式 (timer / compare)"""
        self._node.branch_mode = mode
        self.connection_changed.emit(self._node)
        self.update()
        if self.parent():
            self.parent().update()

    def _set_next_target(self, tid: Optional[str]):
        self._node.next_node_id = tid
        self.connection_changed.emit(self._node)
        if self.parent():
            self.parent().update()

    def _set_trigger_target(self, tid: Optional[str]):
        self._node.on_trigger_target_id = tid
        self.connection_changed.emit(self._node)
        if self.parent():
            self.parent().update()

    def _set_continue_target(self, tid: Optional[str]):
        self._node.on_continue_target_id = tid
        self.connection_changed.emit(self._node)
        if self.parent():
            self.parent().update()

    # ── 節點外觀與端口繪製 ────────────────────────────────────
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = self.width()
        h = self.height()
        cx = w // 2
        cy = 58
        radius = 21

        t_str = str(self._node.type)
        is_branch = ("COUNTER_BRANCH" in t_str)

        # 1. 選取高亮背景框
        if self._is_selected:
            bg_sel = QRect(2, 2, w - 4, h - 4)
            painter.setBrush(QBrush(QColor(30, 58, 138, 70)))
            painter.setPen(QPen(QColor("#38bdf8"), 1.5, Qt.PenStyle.DashLine))
            painter.drawRoundedRect(bg_sel, 8, 8)

        # 2. 決定節點色彩
        branch_mode = getattr(self._node, "branch_mode", "timer")
        d_size = 28  # 菱形尺寸

        if is_branch:
            if branch_mode == "compare":
                circle_color = QColor("#15803d")  # Scratch 經典綠 (Compare 模式)
                border_color = QColor("#4ade80")
            else:
                circle_color = QColor("#b45309")  # 計時琥珀金色 (Timer 模式)
                border_color = QColor("#fde047")
        elif "GAMEPAD" in t_str:
            circle_color = QColor("#c084fc")  # 搖桿：粉紫
            border_color = QColor("#9333ea")
        elif "KEY" in t_str:
            circle_color = QColor("#38bdf8")  # 鍵盤：天藍
            border_color = QColor("#0284c7")
        elif "MOUSE" in t_str:
            circle_color = QColor("#34d399")  # 滑鼠：薄荷綠
            border_color = QColor("#059669")
        elif "WAIT" in t_str:
            circle_color = QColor("#fde047")  # 等待：明黃
            border_color = QColor("#ca8a04")
        else:
            circle_color = QColor("#94a3b8")
            border_color = QColor("#64748b")

        # 3. 頂部角色徽章
        if is_branch:
            role_text = "⏱ TIMER" if branch_mode == "timer" else "🔢 COMPARE"
            badge_bg = QColor("#78350f" if branch_mode == "timer" else "#14532d")
            badge_fg = QColor("#fde68a" if branch_mode == "timer" else "#86efac")
        elif self._index == 0:
            role_text = "➔ ROOT"
            badge_bg = QColor("#0369a1")
            badge_fg = QColor("#38bdf8")
        elif self._index == self._total - 1:
            role_text = "➔ LEAF"
            badge_bg = QColor("#4c1d95")
            badge_fg = QColor("#c084fc")
        else:
            role_text = "➔ NODE"
            badge_bg = QColor("#1e293b")
            badge_fg = QColor("#94a3b8")

        badge_w = 76
        badge_h = 18
        badge_x = cx - badge_w // 2
        badge_y = 6
        painter.setBrush(QBrush(badge_bg))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(QRect(badge_x, badge_y, badge_w, badge_h), 4, 4)

        painter.setPen(badge_fg)
        font_badge = QFont("Consolas", 8, QFont.Weight.Bold)
        painter.setFont(font_badge)
        painter.drawText(QRect(badge_x, badge_y, badge_w, badge_h), Qt.AlignmentFlag.AlignCenter, role_text)

        # 4. 執行中光暈 / 選取光環
        if is_branch:
            diamond_pts = [
                QPoint(cx, cy - d_size),      # 上頂點 (else 出口)
                QPoint(cx + d_size, cy),      # 右頂點 (if / 觸發出口)
                QPoint(cx, cy + d_size),      # 下頂點
                QPoint(cx - d_size, cy)       # 左頂點 (輸入)
            ]
            diamond_poly = QPolygon(diamond_pts)

            if self._is_executing:
                glow_color = QColor(250, 204, 21, 140)
                painter.setBrush(QBrush(glow_color))
                painter.setPen(Qt.PenStyle.NoPen)
                glow_diamond = QPolygon([
                    QPoint(cx, cy - d_size - 6),
                    QPoint(cx + d_size + 6, cy),
                    QPoint(cx, cy + d_size + 6),
                    QPoint(cx - d_size - 6, cy)
                ])
                painter.drawPolygon(glow_diamond)
            elif self._is_selected:
                painter.setBrush(QBrush(QColor(56, 189, 248, 70)))
                painter.setPen(Qt.PenStyle.NoPen)
                glow_diamond = QPolygon([
                    QPoint(cx, cy - d_size - 4),
                    QPoint(cx + d_size + 4, cy),
                    QPoint(cx, cy + d_size + 4),
                    QPoint(cx - d_size - 4, cy)
                ])
                painter.drawPolygon(glow_diamond)

            # 5. 繪製菱形主體 (如圖 1 菱形 If/Else 方塊)
            painter.setBrush(QBrush(circle_color))
            painter.setPen(QPen(border_color, 2.5))
            painter.drawPolygon(diamond_poly)

            # 🎯 如圖 1 在頂部出口處醒目標註 "else"
            font_else = QFont("Consolas", 9, QFont.Weight.Bold)
            painter.setFont(font_else)
            painter.setPen(QColor("#fb7185"))
            painter.drawText(QRect(cx + 6, cy - d_size - 14, 40, 16), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, "else")

            # 菱形內部文字 (如圖 2 Scratch 綠色積木)
            var_name = getattr(self._node, "var_name", "X")
            painter.setPen(QColor("#ffffff"))
            font_diamond_title = QFont("Consolas", 8, QFont.Weight.Bold)
            painter.setFont(font_diamond_title)

            if branch_mode == "compare":
                op = getattr(self._node, "compare_op", ">")
                target = getattr(self._node, "compare_target", 50)
                line1 = f"{var_name}"
                line2 = f"{op} {target}"
            else:
                is_rnd = getattr(self._node, "is_random_target", False)
                if is_rnd:
                    line1 = f"🎲{var_name}"
                    line2 = f"{getattr(self._node, 'random_min', 1.0)}~{getattr(self._node, 'random_max', 5.0)}s"
                else:
                    line1 = f"⏱{var_name}"
                    line2 = f"{getattr(self._node, 'timer_seconds', 3.0)}s"

            # 繪製內部兩行精準置中文字
            painter.drawText(QRect(cx - d_size + 2, cy - 14, (d_size - 2) * 2, 13), Qt.AlignmentFlag.AlignCenter, line1)
            painter.setPen(QColor("#fef08a"))
            font_diamond_sub = QFont("Consolas", 7, QFont.Weight.Bold)
            painter.setFont(font_diamond_sub)
            painter.drawText(QRect(cx - d_size + 2, cy - 1, (d_size - 2) * 2, 13), Qt.AlignmentFlag.AlignCenter, line2)

        else:
            # 普通節點繪製圓圈
            if self._is_executing:
                glow_color = QColor(250, 204, 21, 140)
                painter.setBrush(QBrush(glow_color))
                painter.setPen(Qt.PenStyle.NoPen)
                painter.drawEllipse(QPoint(cx, cy), radius + 7, radius + 7)
                circle_color = QColor("#fde047")
                border_color = QColor("#ca8a04")
            elif self._is_selected:
                painter.setBrush(QBrush(QColor(56, 189, 248, 80)))
                painter.setPen(Qt.PenStyle.NoPen)
                painter.drawEllipse(QPoint(cx, cy), radius + 5, radius + 5)

            # 5. 繪製中央圓圈頂點
            painter.setBrush(QBrush(circle_color))
            painter.setPen(QPen(border_color, 2.5))
            painter.drawEllipse(QPoint(cx, cy), radius, radius)

            t_enum = self._node.type
            if t_enum in (NodeType.KEY_CLICK, NodeType.KEY_DOWN, NodeType.KEY_UP) and self._node.key:
                k = self._node.key.upper()
                mapping = {
                    "SPACE": "␣", "ENTER": "↵", "BACKSPACE": "⌫", "TAB": "⇥",
                    "ESCAPE": "ESC", "DELETE": "DEL", "INSERT": "INS", "UP": "↑",
                    "DOWN": "↓", "LEFT": "←", "RIGHT": "→", "PAGEUP": "PU",
                    "PAGEDOWN": "PD", "LCTRL": "CTRL", "RCTRL": "CTRL",
                    "LSHIFT": "SHFT", "RSHIFT": "SHFT", "LALT": "ALT",
                    "RALT": "ALT", "LWIN": "WIN", "RWIN": "WIN",
                }
                label_text = mapping.get(k, k)
            elif t_enum == NodeType.MOUSE_CLICK:
                b_map = {"left": "🖱左", "right": "🖱右", "middle": "🖱中"}
                btn = getattr(self._node, "button", "left")
                label_text = b_map.get(str(btn).lower(), "🖱")
            elif t_enum == NodeType.MOUSE_MOVE:
                label_text = "🖱移"
            elif t_enum == NodeType.MOUSE_SCROLL:
                label_text = "滾輪"
            elif t_enum == NodeType.GAMEPAD_BUTTON:
                btn = getattr(self._node, "gamepad_button", "A")
                label_text = f"🎮{btn}"
            elif t_enum == NodeType.GAMEPAD_AXIS:
                ax = getattr(self._node, "gamepad_axis", "LX")
                label_text = str(ax).upper()
            elif t_enum in (NodeType.WAIT_FIXED, NodeType.WAIT_RANDOM):
                label_text = "⏱"
            else:
                letters = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
                label_text = letters[self._index] if self._index < len(letters) else f"{self._index + 1:02d}"

            # 依字元長度動態調整字體大小，確保完整清晰居中
            if len(label_text) <= 2:
                font_size = 13
            elif len(label_text) == 3:
                font_size = 10
            elif len(label_text) == 4:
                font_size = 8
            else:
                font_size = 7

            painter.setPen(QColor("#0f172a"))
            font_circle = QFont("Consolas", font_size, QFont.Weight.Bold)
            painter.setFont(font_circle)
            painter.drawText(QRect(cx - radius, cy - radius, radius * 2, radius * 2), Qt.AlignmentFlag.AlignCenter, label_text)

        # 6. 下方文字標籤 (第1行動作類型，第2行明確標示「按下時間 / 範圍」)
        painter.setPen(QColor("#ffffff" if not self._is_selected else "#38bdf8"))
        font_name = QFont("Consolas", 9, QFont.Weight.Bold)
        painter.setFont(font_name)
        text_rect_name = QRect(4, cy + radius + 8, w - 8, 20)

        t_enum = self._node.type
        if is_branch:
            var_name = getattr(self._node, "var_name", "X")
            if branch_mode == "compare":
                op = getattr(self._node, "compare_op", ">")
                tgt = getattr(self._node, "compare_target", 50)
                disp_name = f"判斷 [{var_name} {op} {tgt}]"
            else:
                is_rnd = getattr(self._node, "is_random_target", False)
                if is_rnd:
                    disp_name = f"計時變數 [{var_name}] 隨機"
                else:
                    disp_name = f"計時變數 [{var_name}] {self._node.timer_seconds}s"
        elif t_enum in (NodeType.KEY_CLICK, NodeType.KEY_DOWN, NodeType.KEY_UP):
            act = "點擊" if t_enum == NodeType.KEY_CLICK else ("按下" if t_enum == NodeType.KEY_DOWN else "釋放")
            disp_name = f"{act} [{self._node.key.upper()}]"
        elif t_enum == NodeType.MOUSE_CLICK:
            b_name = "左鍵" if self._node.button == "left" else ("右鍵" if self._node.button == "right" else "中鍵")
            act = "點擊" if self._node.click_type in ("single", "click") else ("按下" if self._node.click_type == "down" else "釋放")
            disp_name = f"滑鼠{b_name} {act}"
        else:
            disp_name = self._node.get_display_name()

        truncated_name = disp_name if len(disp_name) <= 15 else disp_name[:14] + "…"
        painter.drawText(text_rect_name, Qt.AlignmentFlag.AlignCenter, truncated_name)

        # 次要時長資訊 / 變數範圍資訊
        sub_text = ""
        is_highlight_time = False
        if is_branch:
            var_name = getattr(self._node, "var_name", "X")
            end_id = getattr(self._node, "var_scope_end_node_id", None)
            if end_id:
                # 尋找結束節點標籤
                letters = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
                end_tag = None
                for idx, n in enumerate(self._all_nodes):
                    if n.id == end_id:
                        end_tag = letters[idx] if idx < len(letters) else f"{idx+1}"
                        break
                sub_text = f"範圍: 至節點[{end_tag}]" if end_tag else "範圍: 指定結束"
                is_highlight_time = True
            else:
                sub_text = "範圍: 達標自動消除"
        elif t_enum == NodeType.KEY_CLICK and getattr(self._node, "key_hold_ms", 0) > 0:
            sub_text = f"按下: {self._node.key_hold_ms}ms"
            is_highlight_time = True
        elif t_enum in (NodeType.KEY_DOWN, NodeType.KEY_UP) and getattr(self._node, "timestamp_ms", 0) > 0:
            sub_text = f"按下: +{self._node.timestamp_ms}ms"
            is_highlight_time = True
        elif t_enum == NodeType.MOUSE_CLICK and getattr(self._node, "timestamp_ms", 0) > 0:
            sub_text = f"按下: +{self._node.timestamp_ms}ms"
            is_highlight_time = True
        elif t_enum == NodeType.WAIT_FIXED:
            sub_text = f"等待 {self._node.duration_ms}ms"
        elif t_enum == NodeType.WAIT_RANDOM:
            sub_text = f"隨機 {self._node.min_ms}~{self._node.max_ms}ms"
        elif t_enum == NodeType.GAMEPAD_AXIS:
            dur = getattr(self._node, "axis_duration_ms", 0)
            sub_text = f"{dur}ms" if dur > 0 else "瞬間"
        elif t_enum == NodeType.MOUSE_MOVE and getattr(self._node, "move_duration_ms", 0) > 0:
            sub_text = f"耗時 {self._node.move_duration_ms}ms"
        elif getattr(self._node, "comment", ""):
            sub_text = self._node.comment
        elif getattr(self._node, "timestamp_ms", 0) > 0:
            sub_text = f"+{self._node.timestamp_ms}ms"

        if sub_text:
            painter.setPen(QColor("#38bdf8" if is_highlight_time else "#94a3b8"))
            font_sub = QFont("Consolas", 8, QFont.Weight.Bold if is_highlight_time else QFont.Weight.Normal)
            painter.setFont(font_sub)
            text_rect_sub = QRect(4, cy + radius + 28, w - 8, 16)
            painter.drawText(text_rect_sub, Qt.AlignmentFlag.AlignCenter, sub_text)

        # ── 7. 繪製輸入端口與輸出端口 (含磁吸高亮與懸停動畫，100% 完整圓形) ────
        # (A) 左側輸入端口 (Input Port)
        in_pt = QPoint(cx - d_size, cy) if is_branch else QPoint(14, 58)
        if self._is_input_snapped:
            # 🧲 磁吸高亮中！繪製亮綠色擴散光圈
            painter.setBrush(QBrush(QColor(74, 222, 128, 90)))
            painter.setPen(QPen(QColor("#4ade80"), 2))
            painter.drawEllipse(in_pt, 10, 10)
            # 核心實心小球
            painter.setBrush(QBrush(QColor("#4ade80")))
            painter.setPen(QPen(QColor("#08080f"), 1.5))
            painter.drawEllipse(in_pt, 6, 6)
        else:
            # 一般狀態
            painter.setBrush(QBrush(QColor("#38bdf8")))
            painter.setPen(QPen(QColor("#0f172a"), 1.5))
            painter.drawEllipse(in_pt, PORT_RADIUS, PORT_RADIUS)

        # (B) 右側輸出端口 (Output Ports)
        if not is_branch:
            out_pt = QPoint(w - 14, 58)
            is_hov = (self._hovered_port == "normal" or self._is_wiring)
            r = 7 if is_hov else PORT_RADIUS
            if is_hov:
                painter.setBrush(QBrush(QColor(56, 189, 248, 80)))
                painter.setPen(Qt.PenStyle.NoPen)
                painter.drawEllipse(out_pt, r + 4, r + 4)
            painter.setBrush(QBrush(QColor("#38bdf8")))
            painter.setPen(QPen(QColor("#0f172a"), 1.5))
            painter.drawEllipse(out_pt, r, r)
        else:
            # 觸發端口 / If 端口 (右頂點)
            trig_pt = QPoint(cx + d_size, cy)
            is_hov_trig = (self._hovered_port == "trigger" or (self._is_wiring and self._wiring_port == "trigger"))
            r_t = 7 if is_hov_trig else PORT_RADIUS
            if is_hov_trig:
                painter.setBrush(QBrush(QColor(74, 222, 128, 90)))
                painter.setPen(Qt.PenStyle.NoPen)
                painter.drawEllipse(trig_pt, r_t + 4, r_t + 4)
            painter.setBrush(QBrush(QColor("#4ade80")))
            painter.setPen(QPen(QColor("#0f172a"), 1.5))
            painter.drawEllipse(trig_pt, r_t, r_t)

            # 繼續端口 / Else 端口 (如圖 1 上頂點出口)
            cont_pt = QPoint(cx, cy - d_size)
            is_hov_cont = (self._hovered_port == "continue" or (self._is_wiring and self._wiring_port == "continue"))
            r_c = 7 if is_hov_cont else PORT_RADIUS
            if is_hov_cont:
                painter.setBrush(QBrush(QColor(248, 113, 113, 90)))
                painter.setPen(Qt.PenStyle.NoPen)
                painter.drawEllipse(cont_pt, r_c + 4, r_c + 4)
            painter.setBrush(QBrush(QColor("#fb7185")))
            painter.setPen(QPen(QColor("#0f172a"), 1.5))
            painter.drawEllipse(cont_pt, r_c, r_c)


class AovGraphArea(QWidget):
    """
    自由節點圖形區域 (含深色科技網格窗格、拉線箭頭互動與後級輸入端磁吸)
    """
    def __init__(self, canvas: Optional['HorizontalAovCanvas'] = None, parent=None):
        super().__init__(parent)
        self._canvas = canvas
        self.setAcceptDrops(True)
        self.setMinimumSize(3600, 2600)  # 超寬廣網格畫布
        self.setMouseTracking(True)

        # ── 拖曳拉線互動狀態 ──
        self._is_wiring = False
        self._wiring_source_item: Optional[HorizontalAovNodeItem] = None
        self._wiring_port_type: str = "normal"  # "normal" / "trigger" / "continue"
        self._wiring_start_pt = QPoint()
        self._wiring_current_pt = QPoint()
        self._snapped_target_item: Optional[HorizontalAovNodeItem] = None

        # ── 連線點選與刪除 ──
        self._drawn_edges: List[Dict] = []
        self._selected_edge: Optional[Dict] = None

        # ── 中鍵平移 ──
        self._is_panning = False
        self._pan_start_pos = QPoint()
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def _get_canvas_items(self) -> List[HorizontalAovNodeItem]:
        """安全取得畫布上所有節點 Widget"""
        if self._canvas and hasattr(self._canvas, "_items"):
            return self._canvas._items
        parent_obj = self.parent()
        if parent_obj and hasattr(parent_obj, "_items"):
            return parent_obj._items
        return []

    # ── 拉線互動控制 ──────────────────────────────────────────
    def start_wiring(self, source_item: HorizontalAovNodeItem, port_type: str):
        """由節點輸出小圓點被按下時啟動拉線"""
        self._is_wiring = True
        self._wiring_source_item = source_item
        self._wiring_port_type = port_type

        if port_type == "trigger":
            self._wiring_start_pt = source_item.get_trigger_port_pos()
        elif port_type == "continue":
            self._wiring_start_pt = source_item.get_continue_port_pos()
        else:
            self._wiring_start_pt = source_item.get_output_port_pos()

        self._wiring_current_pt = self._wiring_start_pt
        self._snapped_target_item = None
        self._selected_edge = None
        self.update()

    def update_wiring(self, mouse_canvas_pt: QPoint):
        """滑鼠移動時更新拉線軌跡，並對所有後級節點輸入端進行磁吸判定"""
        if not self._is_wiring or not self._wiring_source_item:
            return

        self._wiring_current_pt = mouse_canvas_pt
        items = self._get_canvas_items()

        # 🧲 磁吸判定：尋找距離小於 50px 的後級輸入孔
        SNAP_RADIUS = 50
        closest_dist = SNAP_RADIUS + 1
        best_target = None

        for it in items:
            if it == self._wiring_source_item:
                continue  # 排除自身
            in_port = it.get_input_port_pos()
            dist = math.hypot(mouse_canvas_pt.x() - in_port.x(), mouse_canvas_pt.y() - in_port.y())
            if dist < closest_dist:
                closest_dist = dist
                best_target = it

        # 若在磁吸範圍內，箭頭端點自動「磁吸吸附」到輸入孔！
        if best_target:
            self._snapped_target_item = best_target
            self._wiring_current_pt = best_target.get_input_port_pos()
        else:
            self._snapped_target_item = None

        # 通知各節點更新輸入孔的高亮磁吸光圈
        for it in items:
            it.set_input_snapped(it == self._snapped_target_item)

        self.update()

    def finish_wiring(self):
        """放開滑鼠：若已吸附目標節點，正式建立連線！"""
        if not self._is_wiring:
            return

        items = self._get_canvas_items()
        for it in items:
            it.set_input_snapped(False)

        if self._wiring_source_item and self._snapped_target_item:
            source_node = self._wiring_source_item.node
            target_node = self._snapped_target_item.node

            if self._wiring_port_type == "trigger":
                source_node.on_trigger_target_id = target_node.id
            elif self._wiring_port_type == "continue":
                source_node.on_continue_target_id = target_node.id
            else:
                source_node.next_node_id = target_node.id

            self._wiring_source_item.connection_changed.emit(source_node)

        self._is_wiring = False
        self._wiring_source_item = None
        self._snapped_target_item = None
        self.update()

    def delete_selected_edge(self):
        """刪除選中的連線箭頭"""
        if not self._selected_edge:
            return
        edge = self._selected_edge
        source_item = edge.get("source_item")
        if source_item:
            node = source_item.node
            ptype = edge.get("port_type", "normal")
            if ptype == "trigger":
                node.on_trigger_target_id = None
            elif ptype == "continue":
                node.on_continue_target_id = None
            else:
                node.next_node_id = "__END__"
            source_item.connection_changed.emit(node)
        self._selected_edge = None
        self.update()

    def mousePressEvent(self, event):
        # 1. 中鍵按下 ➔ 平移畫布
        if event.button() == Qt.MouseButton.MiddleButton:
            self._is_panning = True
            self._pan_start_pos = event.globalPosition().toPoint()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()
            return

        # 2. 左鍵點擊 ➔ 檢測是否點中某條箭頭貝茲曲線
        if event.button() == Qt.MouseButton.LeftButton:
            click_pt = event.pos()
            hit_edge = None
            for edge in self._drawn_edges:
                path = edge.get("path")
                if path:
                    stroker = QtGui.QPainterPathStroker()
                    stroker.setWidth(14)
                    stroke_path = stroker.createStroke(path)
                    if stroke_path.contains(click_pt):
                        hit_edge = edge
                        break

            if hit_edge:
                self._selected_edge = hit_edge
                if self._canvas:
                    self._canvas.clear_node_selection()
                self.setFocus()
                self.update()
                event.accept()
                return
            else:
                if self._selected_edge is not None:
                    self._selected_edge = None
                    self.update()

        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        # 中鍵拖曳 ➔ 平移畫布
        if self._is_panning:
            delta = event.globalPosition().toPoint() - self._pan_start_pos
            self._pan_start_pos = event.globalPosition().toPoint()
            if self._canvas:
                hbar = self._canvas.horizontalScrollBar()
                vbar = self._canvas.verticalScrollBar()
                hbar.setValue(hbar.value() - delta.x())
                vbar.setValue(vbar.value() - delta.y())
            event.accept()
            return

        if self._is_wiring:
            self.update_wiring(event.pos())
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.MiddleButton:
            self._is_panning = False
            self.setCursor(Qt.CursorShape.ArrowCursor)
            event.accept()
            return

        if self._is_wiring:
            self.finish_wiring()
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            if self._selected_edge:
                self.delete_selected_edge()
                event.accept()
                return
        super().keyPressEvent(event)

    def contextMenuEvent(self, event):
        """畫布空白處右鍵選單：新增鍵盤、滑鼠、手把、等待、雙輸出分支等節點"""
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: #1e293b;
                color: #f8fafc;
                border: 1px solid #3b82f6;
                border-radius: 6px;
                padding: 4px;
                font-size: 13px;
                font-family: Consolas, monospace;
            }
            QMenu::item {
                padding: 7px 22px 7px 14px;
                border-radius: 4px;
            }
            QMenu::item:selected {
                background-color: #2563eb;
                color: #ffffff;
            }
            QMenu::separator {
                height: 1px;
                background-color: #334155;
                margin: 4px 6px;
            }
        """)

        # 記錄右鍵點擊的畫布座標（吸附網格）
        zoom = getattr(self._canvas, "_zoom_factor", 1.0) if self._canvas else 1.0
        click_world_x = round((event.pos().x() / zoom) / GRID_SIZE) * GRID_SIZE
        click_world_y = round((event.pos().y() / zoom) / GRID_SIZE) * GRID_SIZE

        # ── 1. 鍵盤動作 ──
        menu_kb = menu.addMenu("⌨️  新增鍵盤動作...")
        act_k_click = menu_kb.addAction("⌨ 按鍵點擊 (Click)")
        act_k_click.triggered.connect(lambda: self._request_add_node(NodeType.KEY_CLICK, click_world_x, click_world_y))
        act_k_down = menu_kb.addAction("⬇ 按鍵按下 (Hold/Down)")
        act_k_down.triggered.connect(lambda: self._request_add_node(NodeType.KEY_DOWN, click_world_x, click_world_y))
        act_k_up = menu_kb.addAction("⬆ 按鍵釋放 (Release/Up)")
        act_k_up.triggered.connect(lambda: self._request_add_node(NodeType.KEY_UP, click_world_x, click_world_y))

        # ── 2. 滑鼠動作 ──
        menu_mouse = menu.addMenu("🖱️  新增滑鼠動作...")
        act_m_click = menu_mouse.addAction("🖱 滑鼠點擊 (Click)")
        act_m_click.triggered.connect(lambda: self._request_add_node(NodeType.MOUSE_CLICK, click_world_x, click_world_y))
        act_m_move = menu_mouse.addAction("🎯 滑鼠移動 (Move)")
        act_m_move.triggered.connect(lambda: self._request_add_node(NodeType.MOUSE_MOVE, click_world_x, click_world_y))
        act_m_scroll = menu_mouse.addAction("↕ 滑鼠滾輪 (Scroll)")
        act_m_scroll.triggered.connect(lambda: self._request_add_node(NodeType.MOUSE_SCROLL, click_world_x, click_world_y))

        # ── 3. 手把 / 搖桿動作 ──
        menu_pad = menu.addMenu("🎮  新增手把動作...")
        act_pad_btn = menu_pad.addAction("🎮 搖桿按鍵 (A, B, X, Y...)")
        act_pad_btn.triggered.connect(lambda: self._request_add_node(NodeType.GAMEPAD_BUTTON, click_world_x, click_world_y))
        act_pad_axis = menu_pad.addAction("🕹️ 搖桿推桿 (Axis LX/LY/RX/RY)")
        act_pad_axis.triggered.connect(lambda: self._request_add_node(NodeType.GAMEPAD_AXIS, click_world_x, click_world_y))

        # ── 4. 時間等待 ──
        menu_wait = menu.addMenu("⏱️  新增時間延遲...")
        act_wait_f = menu_wait.addAction("⏱ 固定等待毫秒 (Wait)")
        act_wait_f.triggered.connect(lambda: self._request_add_node(NodeType.WAIT_FIXED, click_world_x, click_world_y))
        act_wait_r = menu_wait.addAction("🎲 隨機等待區間 (Random)")
        act_wait_r.triggered.connect(lambda: self._request_add_node(NodeType.WAIT_RANDOM, click_world_x, click_world_y))

        # ── 5. 雙輸出分支 ──
        act_branch = menu.addAction("⏳  新增計時變數 X (雙輸出分支)")
        act_branch.triggered.connect(lambda: self._request_add_node(NodeType.COUNTER_BRANCH, click_world_x, click_world_y))

        menu.addSeparator()

        # 重置縮放
        act_zoom_reset = menu.addAction("🔍  重置畫布縮放 (100%)")
        act_zoom_reset.triggered.connect(lambda: self._canvas.apply_zoom(1.0, QPoint(0, 0)) if self._canvas else None)

        menu.exec(event.globalPos())

    def _request_add_node(self, node_type: str, x: float = 0.0, y: float = 0.0):
        if self._canvas:
            self._canvas.add_node_at_pos_requested.emit(node_type, x, y)

    # ── 畫布繪製：深色網格窗格 + 所有箭頭連線 + 拖曳中拉線 ────
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = self.width()
        h = self.height()

        # ── 1. 繪製深色科技網格窗格 (Grid Pattern) ─────────────
        painter.fillRect(0, 0, w, h, QColor("#08080f"))

        pen_grid_fine = QPen(QColor("#131320"), 1, Qt.PenStyle.SolidLine)
        pen_grid_major = QPen(QColor("#1e1e32"), 1.2, Qt.PenStyle.SolidLine)

        for x in range(0, w, GRID_SIZE):
            painter.setPen(pen_grid_major if x % 100 == 0 else pen_grid_fine)
            painter.drawLine(x, 0, x, h)

        for y in range(0, h, GRID_SIZE):
            painter.setPen(pen_grid_major if y % 100 == 0 else pen_grid_fine)
            painter.drawLine(0, y, w, y)

        # ── 2. 繪製所有固定連線與導向箭頭 ─────────────────────
        self._drawn_edges = []
        items = self._get_canvas_items()
        if not items:
            return

        node_item_map: Dict[str, HorizontalAovNodeItem] = {it.node.id: it for it in items}

        # ── 2.1 繪製區域變數作用範圍 (Scope Range) 與結束位置標示 ──
        for it in items:
            node = it.node
            if "COUNTER_BRANCH" in str(node.type):
                end_id = getattr(node, "var_scope_end_node_id", None)
                var_name = getattr(node, "var_name", "X")
                if end_id and end_id in node_item_map:
                    end_it = node_item_map[end_id]
                    # 計算包覆兩節點之邊界範圍框
                    min_x = min(it.x(), end_it.x()) - 16
                    max_x = max(it.x() + it.width(), end_it.x() + end_it.width()) + 16
                    min_y = min(it.y(), end_it.y()) - 36
                    max_y = max(it.y() + it.height(), end_it.y() + end_it.height()) + 16
                    scope_rect = QRect(min_x, min_y, max_x - min_x, max_y - min_y)

                    # 範圍底色與科技虛線邊框
                    painter.setBrush(QBrush(QColor(34, 197, 94, 20)))
                    painter.setPen(QPen(QColor(74, 222, 128, 160), 1.8, Qt.PenStyle.DashDotLine))
                    painter.drawRoundedRect(scope_rect, 10, 10)

                    # 範圍左上角標籤
                    lbl_w = 175
                    lbl_rect = QRect(min_x + 8, min_y - 11, lbl_w, 20)
                    painter.setBrush(QBrush(QColor("#064e3b")))
                    painter.setPen(QPen(QColor("#10b981"), 1.2))
                    painter.drawRoundedRect(lbl_rect, 4, 4)
                    painter.setPen(QColor("#6ee7b7"))
                    painter.setFont(QFont("Consolas", 8, QFont.Weight.Bold))
                    painter.drawText(lbl_rect, Qt.AlignmentFlag.AlignCenter, f"⏱️ 變數[{var_name}] 作用範圍 ➔")

                    # 在結束節點上方標記結束消除徽章 (End Marker)
                    end_badge_w = 115
                    end_badge_x = end_it.x() + (end_it.width() - end_badge_w) // 2
                    end_badge_y = end_it.y() - 30
                    end_rect = QRect(end_badge_x, end_badge_y, end_badge_w, 22)
                    painter.setBrush(QBrush(QColor("#450a0a")))
                    painter.setPen(QPen(QColor("#ef4444"), 1.5))
                    painter.drawRoundedRect(end_rect, 5, 5)
                    painter.setPen(QColor("#fca5a5"))
                    painter.setFont(QFont("Consolas", 8, QFont.Weight.Bold))
                    painter.drawText(end_rect, Qt.AlignmentFlag.AlignCenter, f"🏁 [{var_name}] 結束消除")

        for idx, it in enumerate(items):
            node = it.node
            t_str = str(node.type)
            is_branch = ("COUNTER_BRANCH" in t_str)

            if not is_branch:
                # 普通節點連線
                target_id = node.next_node_id
                target_item = None
                if target_id == "__END__":
                    continue
                elif target_id and target_id in node_item_map:
                    target_item = node_item_map[target_id]
                elif target_id is None and idx + 1 < len(items):
                    target_item = items[idx + 1]

                if target_item:
                    p_start = it.get_output_port_pos()
                    p_end = target_item.get_input_port_pos()
                    color = QColor("#38bdf8") if not it._is_executing else QColor("#facc15")
                    edge_dict = {"source_item": it, "target_item": target_item, "port_type": "normal"}
                    self._draw_curve_arrow(painter, p_start, p_end, color, edge_info=edge_dict)

            else:
                # 分支判斷節點（BRANCH）雙連線：
                # (1) ⚡ If / 觸發分支 (右側頂點筆直/平滑輸出)
                trig_id = node.on_trigger_target_id
                if trig_id and trig_id in node_item_map:
                    tgt = node_item_map[trig_id]
                    p_start = it.get_trigger_port_pos()
                    p_end = tgt.get_input_port_pos()
                    edge_dict = {"source_item": it, "target_item": tgt, "port_type": "trigger"}
                    self._draw_curve_arrow(painter, p_start, p_end, QColor("#4ade80"), label="⚡ if", edge_info=edge_dict)

                # (2) ↪ Else / 繼續分支 (如圖 1 頂部 else 折角連線)
                cont_id = node.on_continue_target_id
                if cont_id and cont_id in node_item_map:
                    tgt = node_item_map[cont_id]
                    p_start = it.get_continue_port_pos()
                    p_end = tgt.get_input_port_pos()
                    edge_dict = {"source_item": it, "target_item": tgt, "port_type": "continue"}
                    self._draw_curve_arrow(painter, p_start, p_end, QColor("#fb7185"), label="else", edge_info=edge_dict, port_type="continue")

        # ── 3. 繪製正在拖曳中的連線與磁吸箭頭 ─────────────────
        if self._is_wiring:
            # 判斷連線顏色：若磁吸上目標則變為亮綠色，否則為黃色/青色
            if self._snapped_target_item:
                wire_color = QColor("#4ade80")
            elif self._wiring_port_type == "trigger":
                wire_color = QColor("#4ade80")
            elif self._wiring_port_type == "continue":
                wire_color = QColor("#fb7185")
            else:
                wire_color = QColor("#38bdf8")

            label = "⚡ if" if self._wiring_port_type == "trigger" else ("else" if self._wiring_port_type == "continue" else "")
            self._draw_curve_arrow(painter, self._wiring_start_pt, self._wiring_current_pt, wire_color, label=label, is_wiring=True, port_type=self._wiring_port_type)

    def _draw_curve_arrow(
        self,
        painter: QPainter,
        p1: QPoint,
        p2: QPoint,
        color: QColor,
        label: str = "",
        is_wiring: bool = False,
        edge_info: Optional[Dict] = None,
        port_type: str = "normal"
    ):
        dx = p2.x() - p1.x()
        dy = p2.y() - p1.y()

        path = QPainterPath()
        path.moveTo(QPointF(p1))

        # 🎯 如圖 1：Else 分支從上頂點出發，向上延伸 25px，然後水平折角向右！
        if port_type == "continue":
            up_y = p1.y() - 25
            path.lineTo(QPointF(p1.x(), up_y))
            if p2.x() > p1.x() + 20:
                # 折向右邊
                ctrl_x = max(p1.x() + 30, p2.x() - 35)
                c1 = QPoint(ctrl_x, up_y)
                c2 = QPoint(ctrl_x, p2.y())
                path.cubicTo(QPointF(c1), QPointF(c2), QPointF(p2))
            else:
                ctrl_offset = max(40, abs(dx) * 0.45)
                c1 = QPoint(p1.x(), int(up_y - ctrl_offset))
                c2 = QPoint(int(p2.x() - ctrl_offset), p2.y())
                path.cubicTo(QPointF(c1), QPointF(c2), QPointF(p2))
        elif abs(dy) <= 4:
            # 🎯 水平打直直線連接
            p2_straight = QPoint(p2.x(), p1.y())
            path.lineTo(QPointF(p2_straight))
            c2 = QPoint(p1.x(), p1.y())
        else:
            ctrl_offset = max(40, abs(dx) * 0.45)
            c1 = QPoint(int(p1.x() + ctrl_offset), p1.y())
            c2 = QPoint(int(p2.x() - ctrl_offset), p2.y())
            path.cubicTo(QPointF(c1), QPointF(c2), QPointF(p2))

        if edge_info:
            edge_data = dict(edge_info)
            edge_data["path"] = path
            edge_data["label"] = label
            self._drawn_edges.append(edge_data)

        # 檢測該箭頭是否被選中
        is_selected = False
        if edge_info and self._selected_edge:
            if (self._selected_edge.get("source_item") == edge_info.get("source_item") and
                self._selected_edge.get("port_type") == edge_info.get("port_type")):
                is_selected = True

        # 繪製曲線路徑
        if is_selected:
            # 被選中時：外層白色虛線發光外框
            glow_pen = QPen(QColor(255, 255, 255, 180), 5, Qt.PenStyle.DashLine)
            painter.strokePath(path, glow_pen)
            pen = QPen(QColor("#ffffff"), 2.5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        elif is_wiring:
            glow_pen = QPen(QColor(color.red(), color.green(), color.blue(), 70), 5, Qt.PenStyle.SolidLine)
            painter.strokePath(path, glow_pen)
            pen = QPen(color, 2.5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        else:
            pen = QPen(color, 2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)

        painter.strokePath(path, pen)

        # 終點導向三角箭頭
        arrow_size = 10 if (is_selected or is_wiring) else 8
        arrow_color = QColor("#ffffff") if is_selected else color
        angle = math.atan2(p2.y() - c2.y(), p2.x() - c2.x())
        p_arrow1 = QPoint(
            int(p2.x() - arrow_size * math.cos(angle - math.pi / 6)),
            int(p2.y() - arrow_size * math.sin(angle - math.pi / 6))
        )
        p_arrow2 = QPoint(
            int(p2.x() - arrow_size * math.cos(angle + math.pi / 6)),
            int(p2.y() - arrow_size * math.sin(angle + math.pi / 6))
        )
        arrow = QPolygon([p2, p_arrow1, p_arrow2])
        painter.setBrush(QBrush(arrow_color))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawPolygon(arrow)

        # 標籤文字
        disp_label = label
        if is_selected:
            disp_label = f"{label} [DEL]" if label else "[DEL刪除]"

        if disp_label:
            mid_x = (p1.x() + p2.x()) // 2
            mid_y = (p1.y() + p2.y()) // 2 - 10
            font = QFont("Consolas", 8, QFont.Weight.Bold)
            painter.setFont(font)
            bw = 60 if is_selected else 48
            rect = QRect(mid_x - bw // 2, mid_y - 8, bw, 16)
            painter.setBrush(QBrush(QColor("#08080f")))
            painter.setPen(QPen(arrow_color, 1))
            painter.drawRoundedRect(rect, 3, 3)
            painter.setPen(arrow_color)
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, disp_label)

    def _draw_arrow(self, painter: QPainter, p1: QPoint, p2: QPoint, color: QColor, label: str = ""):
        """繪製直線箭頭"""
        pen = QPen(color, 2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        painter.drawLine(p1, p2)

        arrow_size = 6
        arrow = QPolygon([
            p2,
            QPoint(p2.x() - arrow_size, p2.y() - arrow_size),
            QPoint(p2.x() - arrow_size, p2.y() + arrow_size)
        ])
        painter.setBrush(QBrush(color))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawPolygon(arrow)

        if label:
            font = QFont("Consolas", 8, QFont.Weight.Bold)
            painter.setFont(font)
            rect = QRect(p2.x() + 4, p2.y() - 8, 48, 16)
            painter.setBrush(QBrush(QColor("#08080f")))
            painter.setPen(QPen(color, 1))
            painter.drawRoundedRect(rect, 3, 3)
            painter.setPen(color)
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, label)


class HorizontalAovCanvas(QScrollArea):
    """
    自由網格節點畫布容器
    - 支援節點自由移動、吸附窗格
    - 支援滑鼠在輸出小圓點上拖曳拉線，後級節點輸入端磁吸吸附
    - 支援滑鼠拖曳輸入端斷開連線
    - 支援點擊箭頭按 Delete 鍵刪除連線
    - 支援長按滑鼠中鍵並拖曳平移畫布 (Pan)
    - 支援滑鼠滾輪直接放大縮小 (Zoom)
    """
    node_selected = pyqtSignal(object)       # 傳 node
    delete_requested = pyqtSignal(object)    # 傳 node
    copy_requested = pyqtSignal(object)      # 傳 node
    edit_requested = pyqtSignal(object)      # 傳 node
    add_node_requested = pyqtSignal()        # 點擊＋圓圈
    add_node_at_pos_requested = pyqtSignal(str, float, float) # (node_type, x, y)
    node_dropped = pyqtSignal(str)           # 拖曳放置 node_type
    macro_modified = pyqtSignal()            # 節點位置或連線變更，觸發儲存

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWidgetResizable(False)
        self.setAcceptDrops(True)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setStyleSheet(f"""
            QScrollArea {{
                background-color: {COLORS['bg_primary']};
                border: none;
            }}
            QScrollBar:horizontal, QScrollBar:vertical {{
                background: #090910;
                margin: 0px;
            }}
            QScrollBar:horizontal {{ height: 10px; }}
            QScrollBar:vertical {{ width: 10px; }}
            QScrollBar::handle {{
                background: #252538;
                border-radius: 4px;
            }}
            QScrollBar::handle:hover {{
                background: #3b3b55;
            }}
        """)

        # 縮放比例與平移畫布主體
        self._zoom_factor: float = 1.0
        self._graph_area = AovGraphArea(self)
        self.setWidget(self._graph_area)

        self._nodes: List[MacroNode] = []
        self._items: List[HorizontalAovNodeItem] = []
        self._selected_item: Optional[HorizontalAovNodeItem] = None

    # ── 滾輪放大縮小 (Mouse Wheel Zoom) ───────────────────────
    def wheelEvent(self, event: QWheelEvent):
        """滾輪直接進行畫布縮放 (以滑鼠指針當前位置為中心)"""
        delta = event.angleDelta().y()
        if delta == 0:
            return

        old_zoom = self._zoom_factor
        if delta > 0:
            new_zoom = min(2.2, old_zoom * 1.12)
        else:
            new_zoom = max(0.55, old_zoom / 1.12)

        if abs(new_zoom - old_zoom) > 1e-4:
            self.apply_zoom(new_zoom, event.position().toPoint())
        event.accept()

    def apply_zoom(self, new_zoom: float, mouse_pos: QPoint):
        """套用縮放比例並錨定滑鼠所在內容位置"""
        old_zoom = self._zoom_factor
        self._zoom_factor = new_zoom

        base_w, base_h = 3600, 2600
        self._graph_area.setMinimumSize(int(base_w * new_zoom), int(base_h * new_zoom))
        self._graph_area.resize(int(base_w * new_zoom), int(base_h * new_zoom))

        # 錨定滑鼠指針下的內容座標
        hbar = self.horizontalScrollBar()
        vbar = self.verticalScrollBar()
        ratio = new_zoom / old_zoom
        new_h = int((hbar.value() + mouse_pos.x()) * ratio - mouse_pos.x())
        new_v = int((vbar.value() + mouse_pos.y()) * ratio - mouse_pos.y())
        hbar.setValue(max(0, new_h))
        vbar.setValue(max(0, new_v))

        # 同步更新所有節點位置
        for it in self._items:
            it.update_zoom(new_zoom)

        self._graph_area.update()

    # ── 拖曳接收事件 (Drag & Drop from Toolbox) ───────────────
    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasFormat("application/x-gamescript-node"):
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event):
        if event.mimeData().hasFormat("application/x-gamescript-node"):
            event.acceptProposedAction()
        else:
            super().dragMoveEvent(event)

    def dropEvent(self, event: QDropEvent):
        if event.mimeData().hasFormat("application/x-gamescript-node"):
            node_type = event.mimeData().data("application/x-gamescript-node").data().decode("utf-8")
            event.acceptProposedAction()
            self.node_dropped.emit(node_type)
        else:
            super().dropEvent(event)

    # ── 節點集合管理 ──────────────────────────────────────────
    def set_nodes(self, nodes: List[MacroNode]):
        self._nodes = nodes
        for item in self._items:
            item.deleteLater()
        self._items.clear()
        self._selected_item = None
        if self._graph_area:
            self._graph_area._selected_edge = None

        total = len(nodes)
        for i, n in enumerate(nodes):
            self._create_item(n, i, total)

        self._graph_area.update()

    def add_node_live(self, node: MacroNode):
        """即時新增錄製節點並自動計算單向向右排版座標，確保不重疊且水平打直"""
        total = len(self._items) + 1
        zoom = getattr(self, "_zoom_factor", 1.0)

        # 自動計算向右遞增排版座標 (依序 +220px，水平 Y 對齊)
        if self._items:
            last_item = self._items[-1]
            last_x = getattr(last_item.node, "pos_x", 50.0)
            last_y = getattr(last_item.node, "pos_y", 150.0)
            node.pos_x = max(last_x + 220.0, 50.0 + len(self._items) * 220.0)
            node.pos_y = last_y if last_y > 0 else 150.0
        else:
            node.pos_x = 50.0
            node.pos_y = 150.0

        node.next_node_id = None

        if node not in self._nodes:
            self._nodes.append(node)

        item = self._create_item(node, len(self._items), total)
        for i, it in enumerate(self._items):
            it.set_index(i, total, self._nodes)
        self._graph_area.update()

        # 自動滾動至最新節點
        target_x = int(node.pos_x * zoom)
        self.horizontalScrollBar().setValue(max(0, target_x - 300))

    def update_node_live(self, node: MacroNode):
        """即時更新節點屬性 (如按住時長放開時的更新)"""
        for it in self._items:
            if it.node.id == node.id:
                it.update()
                break
        self._graph_area.update()

    def _create_item(self, node: MacroNode, index: int, total: int) -> HorizontalAovNodeItem:
        item = HorizontalAovNodeItem(node, index, total, self._nodes, self._graph_area)
        item.selected.connect(self._on_item_selected)
        item.delete_requested.connect(self.delete_requested.emit)
        item.copy_requested.connect(self.copy_requested.emit)
        item.edit_requested.connect(self.edit_requested.emit)
        item.node_moved.connect(self._on_node_layout_changed)
        item.connection_changed.connect(self._on_node_layout_changed)

        # 決定初始座標 (優先繼承前級節點 Y 高度，間距 220px 箭頭打直、文字不撞車)
        zoom = getattr(self, "_zoom_factor", 1.0)
        if node.pos_x > 0 or node.pos_y > 0:
            item.move(int(node.pos_x * zoom), int(node.pos_y * zoom))
        else:
            if index > 0 and index - 1 < len(self._nodes):
                prev_n = self._nodes[index - 1]
                auto_x = getattr(prev_n, "pos_x", 50.0) + 220.0
                auto_y = getattr(prev_n, "pos_y", 150.0)
                if auto_y <= 0:
                    auto_y = 150.0
            else:
                auto_x = 50.0 + index * 220.0
                auto_y = 150.0
            item.move(int(auto_x * zoom), int(auto_y * zoom))
            node.pos_x = float(auto_x)
            node.pos_y = float(auto_y)

        item.show()
        self._items.append(item)
        return item

    def _on_node_layout_changed(self, node: MacroNode):
        self._graph_area.update()
        self.macro_modified.emit()

    def clear_node_selection(self):
        """清除所有節點選中狀態"""
        for it in self._items:
            it.set_selected(False)
        self._selected_item = None

    def _on_item_selected(self, item: HorizontalAovNodeItem):
        if self._graph_area:
            self._graph_area._selected_edge = None
        for it in self._items:
            it.set_selected(it == item)
        self._selected_item = item
        self.node_selected.emit(item.node)
        self.setFocus()
        self._graph_area.update()

    def get_selected_node(self) -> Optional[MacroNode]:
        if self._selected_item:
            return self._selected_item.node
        return None

    def highlight_node(self, index: int):
        for i, it in enumerate(self._items):
            it.set_executing(i == index)
        self._graph_area.update()

    def keyPressEvent(self, event: QKeyEvent):
        # 1. 刪除鍵：若選中連線箭頭則刪除連線；若選中節點則刪除節點！
        if event.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            if self._graph_area and getattr(self._graph_area, "_selected_edge", None):
                self._graph_area.delete_selected_edge()
                event.accept()
                return
            elif self._selected_item:
                target_node = self._selected_item.node
                self.delete_requested.emit(target_node)
                event.accept()
                return
        elif event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if self._selected_item:
                self.edit_requested.emit(self._selected_item.node)
                event.accept()
                return
        super().keyPressEvent(event)
