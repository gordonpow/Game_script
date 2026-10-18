"""
巨集回放引擎
負責讀取 MacroNode 序列並透過 InputEngine 注入指令到目標視窗
"""
from __future__ import annotations
import random
import threading
import time
from enum import Enum
from typing import List, Optional, Callable

from models.macro import Macro, PlaybackMode
from models.node import MacroNode, NodeType
from core.input_engine.base import InputEngine
from core.window_manager import WindowManager
from core.logger import log_info, log_debug, log_warn, log_error


class PlayerState(str, Enum):
    IDLE     = "idle"
    RUNNING  = "running"
    PAUSED   = "paused"
    STOPPING = "stopping"


class Player:
    """
    巨集回放引擎
    在獨立執行緒中回放 MacroNode 序列
    """

    def __init__(self, engine: InputEngine, hwnd: int = 0):
        self._engine = engine
        self._hwnd = hwnd
        self._state = PlayerState.IDLE
        self._thread: Optional[threading.Thread] = None
        self._pause_event = threading.Event()
        self._pause_event.set()  # 未暫停時為 set 狀態
        self._stop_flag = threading.Event()

        # 回呼函數
        self._on_state_changed: Optional[Callable[[PlayerState], None]] = None
        self._on_node_executing: Optional[Callable[[int, MacroNode], None]] = None
        self._on_loop_count: Optional[Callable[[int], None]] = None
        self._on_error: Optional[Callable[[str], None]] = None

        # 區域變數與計時器 {var_name: value}
        self._variables: dict = {}
        self._timers: dict = {}
        self._active_scopes: dict = {}  # {var_name: end_node_id}

    def set_target_hwnd(self, hwnd: int):
        self._hwnd = hwnd
        if hasattr(self._engine, "set_target_hwnd"):
            self._engine.set_target_hwnd(hwnd)

    def set_engine(self, engine: InputEngine):
        self._engine = engine

    def set_on_state_changed(self, cb: Callable[[PlayerState], None]):
        self._on_state_changed = cb

    def set_on_node_executing(self, cb: Callable[[int, MacroNode], None]):
        self._on_node_executing = cb

    def set_on_loop_count(self, cb: Callable[[int], None]):
        self._on_loop_count = cb

    def set_on_error(self, cb: Callable[[str], None]):
        self._on_error = cb

    @property
    def state(self) -> PlayerState:
        return self._state

    def _set_state(self, state: PlayerState):
        self._state = state
        if self._on_state_changed:
            self._on_state_changed(state)

    # ── 控制介面 ──────────────────────────────────────────────
    def start(
        self,
        macro: Macro,
        mode: Optional[str] = None,
        loop_count: Optional[int] = None,
        random_delay: Optional[bool] = None,
        min_delay: Optional[int] = None,
        max_delay: Optional[int] = None,
        **kwargs
    ):
        if self._state in (PlayerState.RUNNING, PlayerState.PAUSED):
            return
        self._stop_flag.clear()
        self._pause_event.set()
        self._timers.clear()
        self._variables.clear()
        self._active_scopes.clear()
        self._thread = threading.Thread(
            target=self._run,
            args=(macro, mode, loop_count, random_delay, min_delay, max_delay),
            daemon=True
        )
        self._set_state(PlayerState.RUNNING)
        self._thread.start()

    def pause(self):
        if self._state == PlayerState.RUNNING:
            self._pause_event.clear()
            self._set_state(PlayerState.PAUSED)
            log_info("⏸ [Player] 回放已暫停")

    def resume(self):
        if self._state == PlayerState.PAUSED:
            self._pause_event.set()
            self._set_state(PlayerState.RUNNING)
            log_info("▶ [Player] 回放已繼續")

    def toggle_pause(self):
        if self._state == PlayerState.RUNNING:
            self.pause()
        elif self._state == PlayerState.PAUSED:
            self.resume()

    def stop(self):
        self._stop_flag.set()
        self._pause_event.set()  # 解除暫停，讓執行緒能退出
        self._set_state(PlayerState.STOPPING)
        log_info("⏹ [Player] 正在停止回放...")

    def is_running(self) -> bool:
        return self._state in (PlayerState.RUNNING, PlayerState.PAUSED)

    # ── 回放核心 ──────────────────────────────────────────────
    def _run(
        self,
        macro: Macro,
        mode_override: Optional[str] = None,
        repeat_override: Optional[int] = None,
        random_delay_override: Optional[bool] = None,
        min_delay_override: Optional[int] = None,
        max_delay_override: Optional[int] = None,
    ):
        """主回放執行緒"""
        mode = mode_override if mode_override is not None else macro.playback.mode
        repeat_cnt = repeat_override if repeat_override is not None else macro.playback.repeat_count
        rand_delay = random_delay_override if random_delay_override is not None else macro.playback.random_delay
        min_del = min_delay_override if min_delay_override is not None else macro.playback.random_delay_min_ms
        max_del = max_delay_override if max_delay_override is not None else macro.playback.random_delay_max_ms

        log_info(f"🚀 [Player] 開始回放巨集「{macro.name}」(共 {len(macro.nodes)} 個節點, 模式: {mode})")
        try:
            loop_count = 0
            while not self._stop_flag.is_set():
                loop_count += 1
                log_info(f"🔄 [Player] 進入第 {loop_count} 次循環")
                if self._on_loop_count:
                    self._on_loop_count(loop_count)

                self._execute_nodes(
                    macro.nodes,
                    random_delay=rand_delay,
                    min_delay=min_del,
                    max_delay=max_del
                )

                if self._stop_flag.is_set():
                    break

                if mode == PlaybackMode.ONCE:
                    log_info("✅ [Player] 單次播放完成")
                    break
                elif mode == PlaybackMode.REPEAT:
                    if loop_count >= repeat_cnt:
                        log_info(f"✅ [Player] 已達指定重複次數 ({repeat_cnt})，結束回放")
                        break
                # PlaybackMode.LOOP → 繼續循環

        except Exception as e:
            err = f"回放發生異常: {e}"
            log_error(f"❌ [Player] {err}")
            if self._on_error:
                self._on_error(err)
        finally:
            self._set_state(PlayerState.IDLE)
            log_info("🏁 [Player] 回放任務已完全結束，切回待機狀態")

    def _wait(self, ms: int):
        """可中斷的等待"""
        end = time.time() + ms / 1000.0
        while time.time() < end:
            if self._stop_flag.is_set():
                return
            self._pause_event.wait(timeout=0.02)
            if not self._pause_event.is_set():
                self._pause_event.wait()  # 暫停時阻塞

    def _execute_nodes(self, nodes: List[MacroNode],
                       random_delay: bool = False,
                       min_delay: int = 10, max_delay: int = 50):
        """執行節點序列（支援網格圖形拓撲與自訂箭頭連線跳轉）"""
        if not nodes:
            return

        total = len(nodes)
        node_map = {n.id: n for n in nodes}
        id_to_idx = {n.id: i for i, n in enumerate(nodes)}

        curr_idx = 0
        step_count = 0
        max_steps = max(5000, total * 50)  # 防死循環安全閥
        prev_node: Optional[MacroNode] = None

        while 0 <= curr_idx < total and step_count < max_steps:
            if self._stop_flag.is_set():
                return

            node = nodes[curr_idx]
            step_count += 1

            # 檢查是否有區域變數的作用範圍在此節點結束 (標示消除)
            ended_vars = [v for v, end_id in list(self._active_scopes.items()) if end_id == node.id]
            for v in ended_vars:
                log_info(f"🏁 [區域範圍] 節點 [{curr_idx + 1}] 已到達變數 [{v}] 的作用範圍結束點，消除該變數與計時器")
                self._timers.pop(v, None)
                self._timers.pop(f"{v}_target", None)
                self._variables.pop(v, None)
                self._active_scopes.pop(v, None)

            # 等待暫停解除
            self._pause_event.wait()
            if self._stop_flag.is_set():
                return

            # 時序等待：依據錄製 timestamp 計算與前一個動作的時間差
            if prev_node:
                if node.timestamp_ms > 0 and prev_node.timestamp_ms > 0:
                    delta_ms = node.timestamp_ms - prev_node.timestamp_ms
                    if 0 < delta_ms <= 10000:
                        self._wait(delta_ms)
                else:
                    self._wait(30)

            # 通知 UI 正在執行第幾個節點
            if self._on_node_executing:
                self._on_node_executing(curr_idx, node)

            # 執行節點並取得跳轉指示 (若有自訂連線箭頭)
            type_str = node.type.value if hasattr(node.type, "value") else str(node.type)
            action_info = getattr(node, 'key', '') or getattr(node, 'button', '') or getattr(node, 'gamepad_button', '')
            log_debug(f"[Player] 執行節點 [{curr_idx + 1}/{total}]: {type_str} {action_info}")
            jump_target_id = self._execute_node(node)
            prev_node = node

            # 執行後的隨機真人延遲
            if random_delay:
                delay = random.randint(min_delay, max_delay)
                self._wait(delay)

            # 計算下一個節點索引 (依據使用者調整的連線箭頭)
            if jump_target_id == "__END__":
                log_info(f"⏹ [流程圖] 節點 [{curr_idx + 1}] 連線指向結束，腳本終止")
                break
            elif jump_target_id and jump_target_id in id_to_idx:
                next_idx = id_to_idx[jump_target_id]
                log_debug(f"➔ [流程圖] 依據連線箭頭跳轉至節點 [{next_idx + 1}]")
                curr_idx = next_idx
            else:
                curr_idx += 1


    def _execute_node(self, node: MacroNode):
        """執行單一節點"""
        t = node.type.value if hasattr(node.type, "value") else str(node.type)
        eng = self._engine

        if t in (NodeType.KEY_DOWN, "KEY_DOWN"):
            eng.send_key_down(node.key)

        elif t in (NodeType.KEY_UP, "KEY_UP"):
            eng.send_key_up(node.key)

        elif t in (NodeType.KEY_CLICK, "KEY_CLICK"):
            eng.send_key_down(node.key)
            if node.key_hold_ms > 0:
                self._wait(node.key_hold_ms)
            eng.send_key_up(node.key)

        elif t in (NodeType.MOUSE_MOVE, "MOUSE_MOVE"):
            abs_pos = self._get_abs_pos(node.rel_x, node.rel_y)
            if abs_pos:
                eng.send_mouse_move(*abs_pos)
            if node.move_duration_ms > 0:
                self._wait(node.move_duration_ms)

        elif t in (NodeType.MOUSE_CLICK, "MOUSE_CLICK"):
            abs_pos = self._get_abs_pos(node.rel_x, node.rel_y)
            if abs_pos:
                eng.send_mouse_move(*abs_pos)
            from models.node import MouseClickType
            if node.click_type == MouseClickType.DOWN:
                eng.send_mouse_button_down(node.button)
            elif node.click_type == MouseClickType.UP:
                eng.send_mouse_button_up(node.button)
            else:  # SINGLE or DOUBLE
                eng.send_mouse_button_down(node.button)
                self._wait(50)
                eng.send_mouse_button_up(node.button)
                if node.click_type == MouseClickType.DOUBLE:
                    self._wait(100)
                    eng.send_mouse_button_down(node.button)
                    self._wait(50)
                    eng.send_mouse_button_up(node.button)

        elif t in (NodeType.MOUSE_SCROLL, "MOUSE_SCROLL"):
            eng.send_mouse_scroll(node.scroll_direction, node.scroll_amount)

        elif t in (NodeType.WAIT_FIXED, "WAIT_FIXED"):
            self._wait(node.duration_ms)

        elif t in (NodeType.WAIT_RANDOM, "WAIT_RANDOM"):
            delay = random.randint(node.min_ms, node.max_ms)
            self._wait(delay)

        elif t in (NodeType.GAMEPAD_BUTTON, "GAMEPAD_BUTTON"):
            self._execute_gamepad_button(node)

        elif t in (NodeType.GAMEPAD_AXIS, "GAMEPAD_AXIS"):
            self._execute_gamepad_axis(node)

        elif t in (NodeType.REPEAT_BLOCK, "REPEAT_BLOCK"):
            for _ in range(node.repeat_count):
                if self._stop_flag.is_set():
                    return
                self._execute_nodes(node.children)

        elif t in (NodeType.WAIT_USER_KEY, "WAIT_USER_KEY"):
            self._wait_for_user_key(node.wait_key)

        jump_target = getattr(node, "next_node_id", None)

        if t in (NodeType.COUNTER_BRANCH, "COUNTER_BRANCH"):
            import time
            var_name = getattr(node, "var_name", "X") or "X"
            b_mode = getattr(node, "branch_mode", "timer")

            # 記錄此變數的作用結束節點 ID (若有設定)
            scope_end_id = getattr(node, "var_scope_end_node_id", None)
            if scope_end_id:
                self._active_scopes[var_name] = scope_end_id

            # 確保變數初始值存在 (預設 0.0)
            if var_name not in self._variables:
                init_v = getattr(node, "var_init_val", 0.0)
                self._variables[var_name] = float(init_v)

            is_condition_met = False

            # ── 模式 1: 計時器模式 ──
            if b_mode == "timer":
                now = time.time()
                if var_name not in self._timers:
                    self._timers[var_name] = now
                    # 決定目標數
                    if getattr(node, "is_random_target", False):
                        r_min = getattr(node, "random_min", 1.0)
                        r_max = getattr(node, "random_max", 5.0)
                        target_sec = random.uniform(min(r_min, r_max), max(r_min, r_max))
                        self._timers[f"{var_name}_target"] = target_sec
                        log_info(f"⏳ [計時器模式] 變數 [{var_name}] 啟動隨機目標計時 ({r_min}~{r_max}s，本輪目標: {target_sec:.2f}s)")
                    else:
                        target_sec = float(getattr(node, "timer_seconds", 3.0))
                        self._timers[f"{var_name}_target"] = target_sec
                        log_info(f"⏳ [計時器模式] 變數 [{var_name}] 計時開始 (目標: {target_sec}s)")

                target_sec = self._timers.get(f"{var_name}_target", float(getattr(node, "timer_seconds", 3.0)))
                elapsed = now - self._timers[var_name]
                self._variables[var_name] = elapsed

                if elapsed >= target_sec:
                    is_condition_met = True
                    log_info(f"⚡ [計時器模式] 變數 [{var_name}] 數至目標數 ({elapsed:.2f}s >= {target_sec:.2f}s)，觸發 If 分支！")
                    if getattr(node, "auto_reset_on_target", True):
                        # 數至目標數後自動消除/重置
                        self._timers.pop(var_name, None)
                        self._timers.pop(f"{var_name}_target", None)
                        self._variables[var_name] = float(getattr(node, "var_init_val", 0.0))
                        log_debug(f"🔄 [計時器模式] 變數 [{var_name}] 已達目標數，計數器消除重置至初始值")
                else:
                    log_debug(f"▶ [計時器模式] 變數 [{var_name}] 計時中 ({elapsed:.2f}s / {target_sec:.2f}s)，走 Else 分支")

            # ── 模式 2: 區域變數比較大小模式 (Scratch 綠色比較方塊) ──
            else:
                curr_val = self._variables.get(var_name, float(getattr(node, "var_init_val", 0.0)))
                op = getattr(node, "compare_op", ">")
                target_val = float(getattr(node, "compare_target", 50.0))

                if op == ">":
                    is_condition_met = (curr_val > target_val)
                elif op == "<":
                    is_condition_met = (curr_val < target_val)
                elif op in ("=", "=="):
                    is_condition_met = abs(curr_val - target_val) < 1e-4
                elif op == ">=":
                    is_condition_met = (curr_val >= target_val)
                elif op == "<=":
                    is_condition_met = (curr_val <= target_val)
                elif op == "!=":
                    is_condition_met = abs(curr_val - target_val) >= 1e-4

                res_str = "成立 ➔ If 分支 (右側)" if is_condition_met else "不成立 ➔ Else 分支 (上方)"
                log_info(f"🔀 [變數比較] 判斷 [{var_name}={curr_val} {op} {target_val}] {res_str}")

            # 滿足條件 (If 路線) vs 不滿足 (Else 路線)
            if is_condition_met:
                if node.on_trigger_nodes:
                    self._execute_nodes(node.on_trigger_nodes)
                jump_target = getattr(node, "on_trigger_target_id", None)
            else:
                if node.on_continue_nodes:
                    self._execute_nodes(node.on_continue_nodes)
                jump_target = getattr(node, "on_continue_target_id", None)

        return jump_target


    def _get_abs_pos(self, rel_x: float, rel_y: float):
        if self._hwnd:
            return WindowManager.rel_to_abs(rel_x, rel_y, self._hwnd)
        import ctypes
        sw = ctypes.windll.user32.GetSystemMetrics(0)
        sh = ctypes.windll.user32.GetSystemMetrics(1)
        return (int(rel_x * sw), int(rel_y * sh))

    def _execute_gamepad_button(self, node: MacroNode):
        btn = getattr(node, "gamepad_button", "") or getattr(node, "button", "A")
        btn_str = btn.value if hasattr(btn, "value") else str(btn)
        act = getattr(node, "gamepad_action", "click")
        try:
            from core.vigem_engine import get_vigem_engine
            engine = get_vigem_engine()
            if not engine.is_connected:
                engine.connect(wake_up=False)

            if engine.is_connected:
                hold_ms = getattr(node, "key_hold_ms", 50)
                if hold_ms <= 0:
                    hold_ms = 50
                if act == "down":
                    engine.press_button(btn_str)
                elif act == "up":
                    engine.release_button(btn_str)
                else:
                    engine.press_button(btn_str)
                    self._wait(hold_ms)
                    engine.release_button(btn_str)
                log_debug(f"[Player] 虛擬手把發送按鍵: [{btn_str}] {act} [成功]")
            else:
                log_warn(f"[Player] 虛擬手把尚未連線，無法發送按鍵 [{btn_str}]")
        except Exception as e:
            log_warn(f"[Player] 搖桿發送異常: {e}")

    def _execute_gamepad_axis(self, node: MacroNode):
        try:
            from core.vigem_engine import get_vigem_engine
            engine = get_vigem_engine()
            if not engine.is_connected:
                engine.connect(wake_up=False)
            if engine.is_connected:
                axis_obj = getattr(node, "gamepad_axis", getattr(node, "axis_name", "LX"))
                axis_name = axis_obj.value if hasattr(axis_obj, "value") else str(axis_obj)
                axis_val = getattr(node, "axis_value", 0.0)
                engine.set_axis(axis_name, axis_val)
                log_debug(f"[Player] 虛擬手把推動軸: [{axis_name}] = {axis_val}")
                axis_dur = getattr(node, "axis_duration_ms", 0) or getattr(node, "duration_ms", 0)
                if axis_dur > 0:
                    self._wait(axis_dur)
        except Exception as e:
            log_warn(f"[Player] 搖桿軸發送異常: {e}")


    def _wait_for_user_key(self, wait_key: str):
        """等待使用者按指定鍵（或任意鍵）"""
        done = threading.Event()
        from pynput import keyboard as kb

        def on_press(key):
            if not wait_key:
                done.set()
                return False
            try:
                k = key.char if hasattr(key, "char") and key.char else key.name
                if k and k.lower() == wait_key.lower():
                    done.set()
                    return False
            except Exception:
                pass

        listener = kb.Listener(on_press=on_press)
        listener.start()
        while not done.is_set() and not self._stop_flag.is_set():
            self._pause_event.wait(timeout=0.1)
        listener.stop()
