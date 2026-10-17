"""
鍵鼠錄製引擎
使用 pynput 監聽實體輸入，轉換為 MacroNode 序列
"""
from __future__ import annotations
import threading
import time
from typing import List, Optional, Callable

from dataclasses import dataclass, field
from pynput import keyboard, mouse

from models.node import MacroNode, NodeType, MouseButton, MouseClickType, ScrollDirection
from core.window_manager import WindowManager


@dataclass
class RecordFilter:
    """錄製過濾器設定"""
    record_mouse_move: bool = False
    min_move_interval_ms: int = 50
    record_mouse_click: bool = True
    record_keyboard: bool = True
    record_gamepad: bool = False
    ignore_keys: list = field(default_factory=list)


class Recorder:
    """
    鍵鼠錄製引擎
    錄製實體鍵盤滑鼠操作並轉換為 MacroNode 列表
    """

    def __init__(
        self,
        hwnd: int = 0,
        hotkey_filter: Optional[set] = None,
        record_mouse_move: bool = True,
        target_hwnd: Optional[int] = None,
        filter_config: Optional[RecordFilter] = None,
        **kwargs
    ):
        """
        hwnd / target_hwnd: 目標視窗 HWND（用於計算相對座標，0=全螢幕座標）
        hotkey_filter: 錄製時要過濾掉的熱鍵集合（避免錄進巨集）
        record_mouse_move: 是否錄製滑鼠移動軌跡
        filter_config: 進階錄製過濾器物件
        """
        self._hwnd = target_hwnd if target_hwnd is not None else hwnd
        self._filter = filter_config or RecordFilter()
        if filter_config is not None:
            self._record_mouse_move: bool = filter_config.record_mouse_move
            self._mouse_move_throttle_ms: int = filter_config.min_move_interval_ms
        else:
            self._record_mouse_move: bool = record_mouse_move
            self._mouse_move_throttle_ms: int = 16  # ~60fps

        self._nodes: List[MacroNode] = []
        self._start_time: float = 0.0
        self._recording: bool = False
        self._keyboard_listener: Optional[keyboard.Listener] = None
        self._mouse_listener: Optional[mouse.Listener] = None
        self._last_mouse_pos: tuple = (0, 0)
        self._pressed_keys: set = set()
        self._on_node_added: Optional[Callable[[MacroNode], None]] = None
        self._on_node_updated: Optional[Callable[[MacroNode], None]] = None
        self._on_live_summary: Optional[Callable[[str, MacroNode], None]] = None
        self._active_key_nodes: Dict[str, MacroNode] = {}
        self._active_mouse_nodes: Dict[str, MacroNode] = {}

        # 智慧解析與拆解熱鍵名單（包含組合鍵全名與個別單鍵）
        self._hotkey_filter: set = set()
        if hotkey_filter:
            for item in hotkey_filter:
                if not item:
                    continue
                s = str(item).strip().lower()
                self._hotkey_filter.add(s)
                # 拆解 + 分割鍵 (例如 ctrl+f2 -> ctrl, f2)
                parts = [p.strip().lower() for p in s.split("+") if p.strip()]
                for p in parts:
                    self._hotkey_filter.add(p)
                    if p in ("ctrl", "control"):
                        self._hotkey_filter.update(["ctrl", "lctrl", "rctrl", "control"])
                    elif p == "alt":
                        self._hotkey_filter.update(["alt", "lalt", "ralt"])
                    elif p == "shift":
                        self._hotkey_filter.update(["shift", "lshift", "rshift"])
                    elif p in ("win", "cmd"):
                        self._hotkey_filter.update(["win", "cmd", "lwin", "rwin"])

        # 滑鼠移動節流：最小間隔（毫秒），避免移動節點過多
        self._mouse_move_throttle_ms: int = 16  # ~60fps
        self._last_mouse_move_time: float = 0.0

    def set_target_hwnd(self, hwnd: int):
        self._hwnd = hwnd

    def set_node_added_callback(self, callback: Callable[[MacroNode], None]):
        """每新增一個節點時回呼（用於即時更新 UI）"""
        self._on_node_added = callback

    def set_node_updated_callback(self, callback: Callable[[MacroNode], None]):
        """當節點屬性更新時回呼（如放開按鍵時即時更新按住時間）"""
        self._on_node_updated = callback

    def start(self):
        """開始錄製"""
        if self._recording:
            return
        self._nodes = []
        self._active_key_nodes.clear()
        self._active_mouse_nodes.clear()
        self._recording = True
        self._start_time = time.time()
        self._pressed_keys = set()
        self._last_mouse_move_time = 0.0

        self._keyboard_listener = keyboard.Listener(
            on_press=self._on_key_press,
            on_release=self._on_key_release,
        )
        self._mouse_listener = mouse.Listener(
            on_move=self._on_mouse_move,
            on_click=self._on_mouse_click,
            on_scroll=self._on_mouse_scroll,
        )
        self._keyboard_listener.start()
        self._mouse_listener.start()
        print("[Recorder] 開始錄製")

    def stop(self) -> List[MacroNode]:
        """停止錄製，回傳節點列表"""
        if not self._recording:
            return self._nodes
        self._recording = False
        if self._keyboard_listener:
            self._keyboard_listener.stop()
        if self._mouse_listener:
            self._mouse_listener.stop()
        print(f"[Recorder] 錄製結束，共 {len(self._nodes)} 個節點")
        return self._nodes

    def get_nodes(self) -> List[MacroNode]:
        return list(self._nodes)

    def _timestamp(self) -> int:
        return int((time.time() - self._start_time) * 1000)

    def _key_to_str(self, key) -> str:
        """pynput Key → 字串"""
        try:
            if hasattr(key, "char") and key.char:
                return key.char.lower()
            # Special keys
            name = key.name.lower()
            # 標準化一些名稱
            mapping = {
                "space": "space", "enter": "enter", "backspace": "backspace",
                "tab": "tab", "escape": "escape", "delete": "delete",
                "insert": "insert", "home": "home", "end": "end",
                "page_up": "pageup", "page_down": "pagedown",
                "up": "up", "down": "down", "left": "left", "right": "right",
                "ctrl_l": "lctrl", "ctrl_r": "rctrl",
                "shift_l": "lshift", "shift_r": "rshift",
                "alt_l": "lalt", "alt_r": "ralt",
                "cmd": "win", "cmd_l": "lwin", "cmd_r": "rwin",
                "f1": "f1", "f2": "f2", "f3": "f3", "f4": "f4",
                "f5": "f5", "f6": "f6", "f7": "f7", "f8": "f8",
                "f9": "f9", "f10": "f10", "f11": "f11", "f12": "f12",
            }
            return mapping.get(name, name)
        except Exception:
            return str(key)

    def set_live_summary_callback(self, callback: Callable[[str, MacroNode], None]):
        """設定即時動作文字與節點回呼"""
        self._on_live_summary = callback

    def set_live_callback(self, callback: Callable[[str, MacroNode], None]):
        """即時錄製回呼別名"""
        self._on_live_summary = callback

    def set_ignore_keys(self, keys: list | set):
        """設定要忽略的熱鍵名單"""
        for k in keys:
            if k:
                self._hotkey_filter.add(str(k).strip().lower())

    def _get_rel_pos(self, x: int, y: int):
        if self._hwnd:
            rel = WindowManager.abs_to_rel(x, y, self._hwnd)
            if rel:
                return rel
        # 全螢幕比例
        import ctypes
        sw = ctypes.windll.user32.GetSystemMetrics(0)
        sh = ctypes.windll.user32.GetSystemMetrics(1)
        return (x / sw if sw > 0 else 0.5, y / sh if sh > 0 else 0.5)

    def _is_hotkey(self, key_str: str) -> bool:
        k = key_str.lower().strip()
        if k in self._hotkey_filter:
            return True
        # 兼容帶有 l/r 前綴的修飾鍵
        clean = k.replace("lctrl", "ctrl").replace("rctrl", "ctrl")\
                 .replace("lalt", "alt").replace("ralt", "alt")\
                 .replace("lshift", "shift").replace("rshift", "shift")\
                 .replace("lwin", "win").replace("rwin", "win")
        return clean in self._hotkey_filter

    def _get_node_summary(self, node: MacroNode) -> str:
        """產生簡潔的即時動作描述"""
        if node.type == NodeType.KEY_DOWN:
            return f"⌨ 按下 [{node.key.upper()}]"
        elif node.type == NodeType.KEY_UP:
            return f"⌨ 釋放 [{node.key.upper()}]"
        elif node.type == NodeType.MOUSE_CLICK:
            b_name = "左鍵" if node.button == MouseButton.LEFT else ("右鍵" if node.button == MouseButton.RIGHT else "中鍵")
            act = "按下" if node.click_type == MouseClickType.DOWN else "釋放"
            return f"🖱 滑鼠{b_name} {act} ({int(node.rel_x*100)}%, {int(node.rel_y*100)}%)"
        elif node.type == NodeType.MOUSE_MOVE:
            return f"🖱 滑鼠移動至 ({int(node.rel_x*100)}%, {int(node.rel_y*100)}%)"
        elif node.type == NodeType.MOUSE_SCROLL:
            return f"🖱 滾輪 {node.scroll_direction} ({node.scroll_amount})"
        return f"動作: {node.type.value}"

    def _add_node(self, node: MacroNode):
        self._nodes.append(node)
        summary = self._get_node_summary(node)
        if hasattr(self, "_on_live_summary") and self._on_live_summary:
            try:
                self._on_live_summary(summary, node)
            except Exception:
                pass
        if self._on_node_added:
            try:
                self._on_node_added(node)
            except Exception:
                pass

    # ── 鍵盤事件 ──────────────────────────────────────────────
    def _on_key_press(self, key):
        if not self._recording:
            return
        key_str = self._key_to_str(key)
        if self._is_hotkey(key_str) or key_str in self._pressed_keys:
            return
        self._pressed_keys.add(key_str)
        t = self._timestamp()
        node = MacroNode(
            type=NodeType.KEY_CLICK,
            key=key_str,
            key_hold_ms=50,
            timestamp_ms=t,
        )
        self._active_key_nodes[key_str] = node
        self._add_node(node)

    def _on_key_release(self, key):
        if not self._recording:
            return
        key_str = self._key_to_str(key)
        if self._is_hotkey(key_str):
            return
        self._pressed_keys.discard(key_str)
        t = self._timestamp()
        if key_str in self._active_key_nodes:
            node = self._active_key_nodes.pop(key_str)
            node.key_hold_ms = max(20, t - node.timestamp_ms)
            if hasattr(self, "_on_node_updated") and self._on_node_updated:
                try:
                    self._on_node_updated(node)
                except Exception:
                    pass
        else:
            # 孤立放開
            node = MacroNode(
                type=NodeType.KEY_UP,
                key=key_str,
                timestamp_ms=t,
            )
            self._add_node(node)

    # ── 滑鼠事件 ──────────────────────────────────────────────
    def _on_mouse_move(self, x, y):
        if not self._recording or not self._record_mouse_move:
            return
        now = time.time()
        if (now - self._last_mouse_move_time) * 1000 < self._mouse_move_throttle_ms:
            return
        self._last_mouse_move_time = now
        rel_x, rel_y = self._get_rel_pos(x, y)
        node = MacroNode(
            type=NodeType.MOUSE_MOVE,
            rel_x=rel_x,
            rel_y=rel_y,
            timestamp_ms=self._timestamp(),
        )
        self._add_node(node)

    def _on_mouse_click(self, x, y, button, pressed):
        if not self._recording:
            return
        btn_map = {
            mouse.Button.left:   MouseButton.LEFT,
            mouse.Button.right:  MouseButton.RIGHT,
            mouse.Button.middle: MouseButton.MIDDLE,
        }
        btn_str = btn_map.get(button, MouseButton.LEFT)
        rel_x, rel_y = self._get_rel_pos(x, y)
        t = self._timestamp()
        if pressed:
            node = MacroNode(
                type=NodeType.MOUSE_CLICK,
                rel_x=rel_x,
                rel_y=rel_y,
                button=btn_str,
                click_type=MouseClickType.SINGLE,
                timestamp_ms=t,
            )
            self._active_mouse_nodes[btn_str] = node
            self._add_node(node)
        else:
            if btn_str in self._active_mouse_nodes:
                node = self._active_mouse_nodes.pop(btn_str)
                node.rel_x = rel_x
                node.rel_y = rel_y
                if hasattr(self, "_on_node_updated") and self._on_node_updated:
                    try:
                        self._on_node_updated(node)
                    except Exception:
                        pass

    def _on_mouse_scroll(self, x, y, dx, dy):
        if not self._recording:
            return
        if dy > 0:
            direction = ScrollDirection.UP
            amount = dy
        elif dy < 0:
            direction = ScrollDirection.DOWN
            amount = -dy
        elif dx > 0:
            direction = ScrollDirection.RIGHT
            amount = dx
        else:
            direction = ScrollDirection.LEFT
            amount = -dx
        node = MacroNode(
            type=NodeType.MOUSE_SCROLL,
            scroll_direction=direction,
            scroll_amount=int(amount),
            timestamp_ms=self._timestamp(),
        )
        self._add_node(node)

    @staticmethod
    def optimize_nodes(nodes: List[MacroNode]) -> List[MacroNode]:
        """
        將錄製的原始節點進行智慧配對優化：
        1. 將配對的 KEY_DOWN + KEY_UP 合併為乾淨的 KEY_CLICK 節點
        2. 將成對的 MOUSE DOWN + UP 合併為 MOUSE_CLICK (SINGLE)
        3. 消除多餘重複與打結事件
        """
        if not nodes:
            return []

        result: List[MacroNode] = []
        consumed = set()
        n_len = len(nodes)

        for i in range(n_len):
            if i in consumed:
                continue

            node = nodes[i]

            # ── 1. 鍵盤按下與釋放配對優化 ──
            if node.type == NodeType.KEY_DOWN:
                key_name = node.key.lower()
                matched_up_idx = -1
                for j in range(i + 1, n_len):
                    if j in consumed:
                        continue
                    candidate = nodes[j]
                    if candidate.type == NodeType.KEY_UP and candidate.key.lower() == key_name:
                        matched_up_idx = j
                        break
                    elif candidate.type == NodeType.KEY_DOWN and candidate.key.lower() == key_name:
                        # 連續兩次按下同一鍵，中斷匹配
                        break

                if matched_up_idx != -1:
                    consumed.add(matched_up_idx)
                    up_node = nodes[matched_up_idx]
                    hold_dur = max(20, up_node.timestamp_ms - node.timestamp_ms)
                    merged = MacroNode(
                        type=NodeType.KEY_CLICK,
                        key=node.key,
                        key_hold_ms=hold_dur,
                        timestamp_ms=node.timestamp_ms,
                    )
                    result.append(merged)
                    continue

            # ── 2. 滑鼠按下與釋放配對優化 ──
            elif node.type == NodeType.MOUSE_CLICK and getattr(node, "click_type", None) == MouseClickType.DOWN:
                btn_name = getattr(node, "button", MouseButton.LEFT)
                matched_up_idx = -1
                for j in range(i + 1, min(i + 8, n_len)):
                    if j in consumed:
                        continue
                    candidate = nodes[j]
                    if candidate.type == NodeType.MOUSE_CLICK and getattr(candidate, "click_type", None) == MouseClickType.UP and getattr(candidate, "button", None) == btn_name:
                        matched_up_idx = j
                        break

                if matched_up_idx != -1:
                    consumed.add(matched_up_idx)
                    merged = MacroNode(
                        type=NodeType.MOUSE_CLICK,
                        rel_x=node.rel_x,
                        rel_y=node.rel_y,
                        button=node.button,
                        click_type=MouseClickType.SINGLE,
                        timestamp_ms=node.timestamp_ms,
                    )
                    result.append(merged)
                    continue

            # 略過單獨孤立的 KEY_UP (若前面已被合併)
            if node.type == NodeType.KEY_UP and i in consumed:
                continue

            result.append(node)

        return result
