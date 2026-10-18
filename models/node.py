"""
MacroNode 資料模型
所有巨集節點類型定義
"""
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Dict, Any
import uuid


class NodeType(str, Enum):
    """巨集節點類型"""
    KEY_DOWN        = "KEY_DOWN"        # 按鍵按下
    KEY_UP          = "KEY_UP"          # 按鍵釋放
    KEY_CLICK       = "KEY_CLICK"       # 按鍵點擊（按下+釋放）
    MOUSE_MOVE      = "MOUSE_MOVE"      # 滑鼠移動（相對視窗比例座標）
    MOUSE_CLICK     = "MOUSE_CLICK"     # 滑鼠點擊
    MOUSE_SCROLL    = "MOUSE_SCROLL"    # 滾輪
    WAIT_FIXED      = "WAIT_FIXED"      # 等待固定毫秒
    WAIT_RANDOM     = "WAIT_RANDOM"     # 等待隨機毫秒
    GAMEPAD_BUTTON  = "GAMEPAD_BUTTON"  # 搖桿按鍵
    GAMEPAD_AXIS    = "GAMEPAD_AXIS"    # 搖桿軸推送
    REPEAT_BLOCK    = "REPEAT_BLOCK"    # 重複N次子序列
    WAIT_USER_KEY   = "WAIT_USER_KEY"   # 等待使用者按鍵
    COUNTER_BRANCH  = "COUNTER_BRANCH"  # 計時/計數器雙輸出分支 (變數X, 觸發/未觸發)


class MouseButton(str, Enum):
    """滑鼠按鍵"""
    LEFT    = "left"
    RIGHT   = "right"
    MIDDLE  = "middle"
    X1      = "x1"
    X2      = "x2"


class MouseClickType(str, Enum):
    """滑鼠點擊類型"""
    SINGLE = "single"
    DOUBLE = "double"
    DOWN   = "down"
    UP     = "up"


class ScrollDirection(str, Enum):
    """滾輪方向"""
    UP   = "up"
    DOWN = "down"
    LEFT = "left"
    RIGHT = "right"


class GamepadButtonName(str, Enum):
    """搖桿按鍵名稱（XInput）"""
    A       = "A"
    B       = "B"
    X       = "X"
    Y       = "Y"
    LB      = "LB"
    RB      = "RB"
    LT      = "LT"
    RT      = "RT"
    START   = "START"
    BACK    = "BACK"
    LS      = "LS"
    RS      = "RS"
    DPAD_UP    = "DPAD_UP"
    DPAD_DOWN  = "DPAD_DOWN"
    DPAD_LEFT  = "DPAD_LEFT"
    DPAD_RIGHT = "DPAD_RIGHT"


class GamepadAxisName(str, Enum):
    """搖桿軸名稱"""
    LX = "LX"   # 左搖桿 X
    LY = "LY"   # 左搖桿 Y
    RX = "RX"   # 右搖桿 X
    RY = "RY"   # 右搖桿 Y


@dataclass
class MacroNode:
    """
    通用巨集節點 - 使用單一類別涵蓋所有節點類型
    根據 type 欄位決定哪些欄位有效
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    type: str = NodeType.WAIT_FIXED

    # ── 按鍵欄位 ──
    key: str = ""                           # 按鍵名稱（如 "w", "space", "ctrl"）
    key_hold_ms: int = 0                    # KEY_CLICK 時按住時長

    # ── 滑鼠欄位 ──
    rel_x: float = 0.5                      # 相對視窗寬度比例 (0.0~1.0)
    rel_y: float = 0.5                      # 相對視窗高度比例 (0.0~1.0)
    move_duration_ms: int = 0               # 移動到位的時間（0=瞬間）
    button: str = MouseButton.LEFT          # 滑鼠按鍵
    click_type: str = MouseClickType.SINGLE # 點擊類型
    scroll_direction: str = ScrollDirection.UP
    scroll_amount: int = 3                  # 滾輪格數

    # ── 等待欄位 ──
    duration_ms: int = 500                  # WAIT_FIXED 等待時長
    min_ms: int = 100                       # WAIT_RANDOM 最小等待
    max_ms: int = 500                       # WAIT_RANDOM 最大等待

    # ── 搖桿欄位 ──
    gamepad_button: str = GamepadButtonName.A
    gamepad_action: str = "click"           # "down" / "up" / "click"
    gamepad_axis: str = GamepadAxisName.LX
    axis_value: float = 0.0                 # -1.0 ~ 1.0
    axis_duration_ms: int = 0              # 推桿持續時間（0=瞬間）

    # ── 重複區塊欄位 ──
    repeat_count: int = 1
    children: List["MacroNode"] = field(default_factory=list)

    # ── 等待使用者按鍵欄位 ──
    wait_key: str = ""                      # 空字串 = 任意鍵

    # ── 錄製時間戳 ──
    timestamp_ms: int = 0                   # 相對錄製開始的時間

    # ── 雙輸出計時/比較分支器欄位 (支援 Scratch 形式) ──
    branch_mode: str = "timer"              # 分支模式: "timer" (計時器模式), "compare" (區域變數比較大小)
    var_name: str = "X"                     # 區域變數名稱
    var_init_val: float = 0.0               # 初始值 (預設為 0)
    var_scope_end_node_id: Optional[str] = None  # 區域範圍結束位置節點 ID (標示結束位置並消除)
    
    # ── 計時器模式參數 ──
    timer_seconds: float = 3.0              # 固定目標時長 (秒)
    is_random_target: bool = False          # 是否自定義隨機目標數
    random_min: float = 1.0                 # 隨機目標數下限 (秒)
    random_max: float = 5.0                 # 隨機目標數上限 (秒)
    auto_reset_on_target: bool = True       # 數至目標數後消除/重置計數器
    trigger_type: str = "timeout"           # 觸發條件: "timeout" (時間到), "key_release" (按鍵放開)

    # ── 區域變數比較模式參數 (Scratch 六角形比較積木) ──
    compare_op: str = ">"                   # 比較運算子: ">", "<", "=", ">=", "<=", "!="
    compare_target: float = 50.0            # 比較目標數值 (預設 50)

    on_trigger_nodes: List["MacroNode"] = field(default_factory=list)   # 輸出1: 滿足條件/觸發時執行的操作 (If 分支)
    on_continue_nodes: List["MacroNode"] = field(default_factory=list)  # 輸出2: 不滿足條件/未觸發時操作 (Else 分支)

    # ── 自由網格畫布座標與自訂箭頭連線目標 ──
    pos_x: float = 0.0                      # 畫布 X 座標
    pos_y: float = 0.0                      # 畫布 Y 座標
    next_node_id: Optional[str] = None      # 普通節點箭頭指向的目標節點 ID (None=預設下一個)
    on_trigger_target_id: Optional[str] = None  # 分支節點【If / 觸發】箭頭目標節點 ID
    on_continue_target_id: Optional[str] = None # 分支節點【Else / 繼續】箭頭目標節點 ID

    # ── 顯示用備註 ──
    comment: str = ""

    def get_display_name(self) -> str:
        """取得節點的顯示文字"""
        t = self.type
        if t == NodeType.KEY_DOWN:
            return f"按下 [{self.key.upper()}]"
        elif t == NodeType.KEY_UP:
            return f"釋放 [{self.key.upper()}]"
        elif t == NodeType.KEY_CLICK:
            hold = f" 持{self.key_hold_ms}ms" if self.key_hold_ms > 0 else ""
            return f"點擊 [{self.key.upper()}]{hold}"
        elif t == NodeType.MOUSE_MOVE:
            return f"滑鼠移至 ({self.rel_x:.1%}, {self.rel_y:.1%})"
        elif t == NodeType.MOUSE_CLICK:
            return f"滑鼠{self.click_type} [{self.button}] @ ({self.rel_x:.1%}, {self.rel_y:.1%})"
        elif t == NodeType.MOUSE_SCROLL:
            return f"滾輪 {self.scroll_direction} x{self.scroll_amount}"
        elif t == NodeType.WAIT_FIXED:
            return f"等待 {self.duration_ms} ms"
        elif t == NodeType.WAIT_RANDOM:
            return f"隨機等待 {self.min_ms}~{self.max_ms} ms"
        elif t == NodeType.GAMEPAD_BUTTON:
            return f"搖桿 [{self.gamepad_button}] {self.gamepad_action}"
        elif t == NodeType.GAMEPAD_AXIS:
            ax = getattr(self.gamepad_axis, "value", self.gamepad_axis)
            return f"搖桿軸 {ax} = {self.axis_value:.2f}"
        elif t == NodeType.REPEAT_BLOCK:
            return f"重複 {self.repeat_count} 次 ({len(self.children)} 個節點)"
        elif t == NodeType.WAIT_USER_KEY:
            key_str = f"[{self.wait_key}]" if self.wait_key else "任意鍵"
            return f"等待使用者按 {key_str}"
        elif t == NodeType.COUNTER_BRANCH:
            b_mode = getattr(self, "branch_mode", "timer")
            if b_mode == "compare":
                op = getattr(self, "compare_op", ">")
                tgt = getattr(self, "compare_target", 50.0)
                tgt_str = f"{int(tgt)}" if tgt.is_integer() else f"{tgt:.1f}"
                return f"判斷 [{self.var_name} {op} {tgt_str}]"
            else:
                if getattr(self, "is_random_target", False):
                    return f"計時變數 [{self.var_name}: {self.random_min}~{self.random_max}s]"
                return f"計時變數 [{self.var_name}: {self.timer_seconds}s]"
        return t

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type,
            "key": self.key,
            "key_hold_ms": self.key_hold_ms,
            "rel_x": self.rel_x,
            "rel_y": self.rel_y,
            "move_duration_ms": self.move_duration_ms,
            "button": self.button,
            "click_type": self.click_type,
            "scroll_direction": self.scroll_direction,
            "scroll_amount": self.scroll_amount,
            "duration_ms": self.duration_ms,
            "min_ms": self.min_ms,
            "max_ms": self.max_ms,
            "gamepad_button": self.gamepad_button,
            "gamepad_action": self.gamepad_action,
            "gamepad_axis": self.gamepad_axis,
            "axis_value": self.axis_value,
            "axis_duration_ms": self.axis_duration_ms,
            "repeat_count": self.repeat_count,
            "children": [c.to_dict() for c in self.children],
            "wait_key": self.wait_key,
            "timestamp_ms": self.timestamp_ms,
            "comment": self.comment,
            # 雙輸出分支擴充 (Scratch 形式)
            "branch_mode": getattr(self, "branch_mode", "timer"),
            "var_name": self.var_name,
            "var_init_val": getattr(self, "var_init_val", 0.0),
            "var_scope_end_node_id": getattr(self, "var_scope_end_node_id", None),
            "timer_seconds": self.timer_seconds,
            "is_random_target": getattr(self, "is_random_target", False),
            "random_min": getattr(self, "random_min", 1.0),
            "random_max": getattr(self, "random_max", 5.0),
            "auto_reset_on_target": getattr(self, "auto_reset_on_target", True),
            "compare_op": getattr(self, "compare_op", ">"),
            "compare_target": getattr(self, "compare_target", 50.0),
            "trigger_type": self.trigger_type,
            "on_trigger_nodes": [n.to_dict() for n in self.on_trigger_nodes],
            "on_continue_nodes": [n.to_dict() for n in self.on_continue_nodes],
            # 網格座標與自訂連線
            "pos_x": self.pos_x,
            "pos_y": self.pos_y,
            "next_node_id": self.next_node_id,
            "on_trigger_target_id": self.on_trigger_target_id,
            "on_continue_target_id": self.on_continue_target_id,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "MacroNode":
        node = cls(
            id=d.get("id", str(uuid.uuid4())),
            type=d.get("type", NodeType.WAIT_FIXED),
            key=d.get("key", ""),
            key_hold_ms=d.get("key_hold_ms", 0),
            rel_x=d.get("rel_x", 0.5),
            rel_y=d.get("rel_y", 0.5),
            move_duration_ms=d.get("move_duration_ms", 0),
            button=d.get("button", MouseButton.LEFT),
            click_type=d.get("click_type", MouseClickType.SINGLE),
            scroll_direction=d.get("scroll_direction", ScrollDirection.UP),
            scroll_amount=d.get("scroll_amount", 3),
            duration_ms=d.get("duration_ms", 500),
            min_ms=d.get("min_ms", 100),
            max_ms=d.get("max_ms", 500),
            gamepad_button=d.get("gamepad_button", GamepadButtonName.A),
            gamepad_action=d.get("gamepad_action", "click"),
            gamepad_axis=d.get("gamepad_axis", GamepadAxisName.LX),
            axis_value=d.get("axis_value", 0.0),
            axis_duration_ms=d.get("axis_duration_ms", 0),
            repeat_count=d.get("repeat_count", 1),
            wait_key=d.get("wait_key", ""),
            timestamp_ms=d.get("timestamp_ms", 0),
            comment=d.get("comment", ""),
            # 雙輸出分支擴充
            branch_mode=d.get("branch_mode", "timer"),
            var_name=d.get("var_name", "X"),
            var_init_val=float(d.get("var_init_val", 0.0)),
            var_scope_end_node_id=d.get("var_scope_end_node_id", None),
            timer_seconds=float(d.get("timer_seconds", 3.0)),
            is_random_target=bool(d.get("is_random_target", False)),
            random_min=float(d.get("random_min", 1.0)),
            random_max=float(d.get("random_max", 5.0)),
            auto_reset_on_target=bool(d.get("auto_reset_on_target", True)),
            compare_op=d.get("compare_op", ">"),
            compare_target=float(d.get("compare_target", 50.0)),
            trigger_type=d.get("trigger_type", "timeout"),
            # 網格座標與自訂連線
            pos_x=float(d.get("pos_x", 0.0)),
            pos_y=float(d.get("pos_y", 0.0)),
            next_node_id=d.get("next_node_id", None),
            on_trigger_target_id=d.get("on_trigger_target_id", None),
            on_continue_target_id=d.get("on_continue_target_id", None),
        )
        node.children = [MacroNode.from_dict(c) for c in d.get("children", [])]
        node.on_trigger_nodes = [MacroNode.from_dict(n) for n in d.get("on_trigger_nodes", [])]
        node.on_continue_nodes = [MacroNode.from_dict(n) for n in d.get("on_continue_nodes", [])]
        return node

