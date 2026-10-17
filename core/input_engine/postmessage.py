"""
PostMessage 深度後台輸入引擎
專注於「不搶焦點、不干涉使用者前台操作」的獨立後台視窗注入
支援：
1. 智慧遞迴穿透子視窗 (Chrome_RenderWidgetHostHWND / D3D 渲染控制項 / Edit 等)
2. AttachThreadInput 執行緒輸入橋接 (讓後台視窗識別鍵盤焦點)
3. 完整的 Win32 消息鏈 (WM_KEYDOWN, WM_KEYUP, WM_CHAR, WM_MOUSE*)
4. 嚴格隔離：有指定目標視窗時絕不使用 SendInput 打擾使用者前台
"""
from __future__ import annotations
import ctypes
import ctypes.wintypes
import time
from typing import Optional, List

import win32api
import win32con
import win32gui
import win32process

from core.input_engine.base import InputEngine
from core.logger import log_info, log_debug, log_warn, log_error

# Virtual key code 映射表
VK_MAP: dict[str, int] = {
    "a": 0x41, "b": 0x42, "c": 0x43, "d": 0x44, "e": 0x45,
    "f": 0x46, "g": 0x47, "h": 0x48, "i": 0x49, "j": 0x4A,
    "k": 0x4B, "l": 0x4C, "m": 0x4D, "n": 0x4E, "o": 0x4F,
    "p": 0x50, "q": 0x51, "r": 0x52, "s": 0x53, "t": 0x54,
    "u": 0x55, "v": 0x56, "w": 0x57, "x": 0x58, "y": 0x59,
    "z": 0x5A,
    "0": 0x30, "1": 0x31, "2": 0x32, "3": 0x33, "4": 0x34,
    "5": 0x35, "6": 0x36, "7": 0x37, "8": 0x38, "9": 0x39,
    "space": win32con.VK_SPACE,
    "enter": win32con.VK_RETURN, "return": win32con.VK_RETURN,
    "escape": win32con.VK_ESCAPE, "esc": win32con.VK_ESCAPE,
    "shift": win32con.VK_SHIFT, "lshift": win32con.VK_LSHIFT, "rshift": win32con.VK_RSHIFT,
    "ctrl": win32con.VK_CONTROL, "lctrl": win32con.VK_LCONTROL, "rctrl": win32con.VK_RCONTROL,
    "alt": win32con.VK_MENU, "lalt": win32con.VK_LMENU, "ralt": win32con.VK_RMENU,
    "f1": win32con.VK_F1, "f2": win32con.VK_F2,
    "f3": win32con.VK_F3, "f4": win32con.VK_F4,
    "f5": win32con.VK_F5, "f6": win32con.VK_F6,
    "f7": win32con.VK_F7, "f8": win32con.VK_F8,
    "f9": win32con.VK_F9, "f10": win32con.VK_F10,
    "f11": win32con.VK_F11, "f12": win32con.VK_F12,
    "tab": win32con.VK_TAB,
    "backspace": win32con.VK_BACK,
    "delete": win32con.VK_DELETE, "del": win32con.VK_DELETE,
    "insert": win32con.VK_INSERT,
    "home": win32con.VK_HOME, "end": win32con.VK_END,
    "pageup": win32con.VK_PRIOR, "pagedown": win32con.VK_NEXT,
    "up": win32con.VK_UP, "down": win32con.VK_DOWN,
    "left": win32con.VK_LEFT, "right": win32con.VK_RIGHT,
    "capslock": win32con.VK_CAPITAL,
}


class PostMessageEngine(InputEngine):
    """
    Win32 深度後台輸入引擎
    透過 HWND 消息注入，讓遊戲或應用在後台（非焦點）時也能持續執行，
    且絕對不干涉使用者當前的前台工作與鍵鼠操作。
    """

    def __init__(self, hwnd: int = 0):
        self._hwnd = hwnd
        self._target_child_hwnd: int = 0
        self._initialized = False

    def set_target_hwnd(self, hwnd: int):
        self._hwnd = hwnd
        self._target_child_hwnd = 0  # 重設子視窗快取
        log_info(f"[後台引擎] 更新目標視窗頂層 HWND: {hwnd}")
        self._resolve_target_hwnds()

    def initialize(self) -> bool:
        self._initialized = True
        self._resolve_target_hwnds()
        log_info(f"[後台引擎] 初始化完成 (頂層: {self._hwnd}, 內部接收端: {self._target_child_hwnd or self._hwnd})")
        return True

    def shutdown(self) -> None:
        self._initialized = False
        log_info("[後台引擎] 引擎已關閉")

    def _resolve_target_hwnds(self) -> List[int]:
        """
        智慧解析真正接收輸入的視窗清單
        包含：頂層視窗、底層渲染視窗 (Chrome_RenderWidgetHostHWND, D3D 等)
        """
        if not self._hwnd or not win32gui.IsWindow(self._hwnd):
            return []

        targets = [self._hwnd]
        best_child = None

        def enum_cb(h, _):
            nonlocal best_child
            if not win32gui.IsWindowVisible(h):
                return True
            cls = win32gui.GetClassName(h)
            # 瀏覽器與渲染視窗 (Chrome, Edge, Electron, Qt QWindow 等)
            if "RenderWidgetHost" in cls or "Intermediate D3D" in cls:
                best_child = h
                return False
            # 常見文字編輯區
            if cls.lower() in ("edit", "richedit", "richedit20w", "richedit50w"):
                best_child = h
                return False
            return True

        try:
            win32gui.EnumChildWindows(self._hwnd, enum_cb, None)
        except Exception:
            pass

        if best_child and best_child not in targets:
            self._target_child_hwnd = best_child
            targets.insert(0, best_child)  # 優先向子渲染控制項發送
            log_debug(f"[後台引擎] 偵測到內部渲染控制項: HWND {best_child} ({win32gui.GetClassName(best_child)})")

        return targets

    def _make_lparam(self, vk: int, is_up: bool = False) -> int:
        scan_code = win32api.MapVirtualKey(vk, 0)
        lparam = (scan_code << 16) | 1
        if is_up:
            lparam |= (1 << 30) | (1 << 31)
        return lparam

    def _attach_thread_input_send(self, target_hwnd: int, action_fn):
        """透過 AttachThreadInput 將輸入隊列連接至目標視窗執行緒"""
        try:
            target_tid, _ = win32process.GetWindowThreadProcessId(target_hwnd)
            curr_tid = win32api.GetCurrentThreadId()
            attached = False
            if target_tid and target_tid != curr_tid:
                try:
                    win32process.AttachThreadInput(curr_tid, target_tid, True)
                    attached = True
                except Exception:
                    pass

            result = action_fn()

            if attached:
                try:
                    win32process.AttachThreadInput(curr_tid, target_tid, False)
                except Exception:
                    pass
            return result
        except Exception:
            return action_fn()

    def send_key_down(self, key: str) -> bool:
        k = key.lower()
        vk = VK_MAP.get(k)
        if vk is None:
            log_warn(f"[後台引擎] 未知的按鍵名稱: '{key}'，無法發送")
            return False

        # 若使用者指定了特定視窗，嚴格進行後台注入，絕不打擾前台
        targets = self._resolve_target_hwnds()
        if targets:
            success = False
            for th in targets:
                try:
                    lparam = self._make_lparam(vk, is_up=False)

                    def do_send():
                        # 後台按鍵注入
                        win32gui.PostMessage(th, win32con.WM_KEYDOWN, vk, lparam)
                        # 對於英數字元補充 WM_CHAR
                        if len(k) == 1 and k.isalnum():
                            win32gui.PostMessage(th, win32con.WM_CHAR, ord(k), lparam)

                    self._attach_thread_input_send(th, do_send)
                    success = True
                except Exception as e:
                    log_warn(f"[後台引擎] 發送至 HWND {th} 失敗: {e}")

            if success:
                log_debug(f"[後台引擎] 成功後台發送 KEY_DOWN [{key.upper()}] (目標 HWND: {targets[0]})")
                return True

        # 若未指定視窗 (HWND == 0，全螢幕遊戲)，才使用前台 SendInput 模式
        if not self._hwnd:
            try:
                flags = 0
                scan_code = win32api.MapVirtualKey(vk, 0)
                win32api.keybd_event(vk, scan_code, flags, 0)
                log_debug(f"[後台引擎] (全螢幕模式) 透過 SendInput 發送 KEY_DOWN [{key.upper()}]")
                return True
            except Exception as e:
                log_error(f"[後台引擎] SendInput 失敗: {e}")
                return False

        return False

    def send_key_up(self, key: str) -> bool:
        k = key.lower()
        vk = VK_MAP.get(k)
        if vk is None:
            return False

        targets = self._resolve_target_hwnds()
        if targets:
            success = False
            for th in targets:
                try:
                    lparam = self._make_lparam(vk, is_up=True)

                    def do_send():
                        win32gui.PostMessage(th, win32con.WM_KEYUP, vk, lparam)

                    self._attach_thread_input_send(th, do_send)
                    success = True
                except Exception:
                    pass

            if success:
                log_debug(f"[後台引擎] 成功後台發送 KEY_UP [{key.upper()}] (目標 HWND: {targets[0]})")
                return True

        if not self._hwnd:
            try:
                flags = win32con.KEYEVENTF_KEYUP
                scan_code = win32api.MapVirtualKey(vk, 0)
                win32api.keybd_event(vk, scan_code, flags, 0)
                return True
            except Exception:
                return False

        return False

    def send_mouse_move(self, abs_x: int, abs_y: int) -> bool:
        targets = self._resolve_target_hwnds()
        if targets:
            th = targets[0]
            try:
                rect = win32gui.GetWindowRect(th)
                rel_x = abs_x - rect[0]
                rel_y = abs_y - rect[1]
                lparam = (rel_y << 16) | (rel_x & 0xFFFF)
                win32gui.PostMessage(th, win32con.WM_MOUSEMOVE, 0, lparam)
                log_debug(f"[後台引擎] 後台滑鼠移動至 ({rel_x}, {rel_y}) -> HWND {th}")
                return True
            except Exception as e:
                log_warn(f"[後台引擎] 後台滑鼠移動失敗: {e}")

        if not self._hwnd:
            try:
                win32api.SetCursorPos((abs_x, abs_y))
                return True
            except Exception:
                return False

        return False

    def send_mouse_button_down(self, button: str) -> bool:
        targets = self._resolve_target_hwnds()
        msg_map = {
            "left":   win32con.WM_LBUTTONDOWN,
            "right":  win32con.WM_RBUTTONDOWN,
            "middle": win32con.WM_MBUTTONDOWN,
        }
        msg = msg_map.get(button.lower(), win32con.WM_LBUTTONDOWN)
        if targets:
            th = targets[0]
            try:
                # 後台點擊注入 (不搶焦點)
                win32gui.PostMessage(th, win32con.WM_MOUSEACTIVATE, self._hwnd, (msg << 16) | 1)
                win32gui.PostMessage(th, msg, 0, 0)
                log_debug(f"[後台引擎] 後台發送滑鼠按下 [{button}] -> HWND {th}")
                return True
            except Exception as e:
                log_warn(f"[後台引擎] 後台滑鼠按下失敗: {e}")

        if not self._hwnd:
            try:
                flag_map = {
                    "left":   win32con.MOUSEEVENTF_LEFTDOWN,
                    "right":  win32con.MOUSEEVENTF_RIGHTDOWN,
                    "middle": win32con.MOUSEEVENTF_MIDDLEDOWN,
                }
                win32api.mouse_event(flag_map.get(button.lower(), win32con.MOUSEEVENTF_LEFTDOWN), 0, 0, 0, 0)
                return True
            except Exception:
                return False

        return False

    def send_mouse_button_up(self, button: str) -> bool:
        targets = self._resolve_target_hwnds()
        msg_map = {
            "left":   win32con.WM_LBUTTONUP,
            "right":  win32con.WM_RBUTTONUP,
            "middle": win32con.WM_MBUTTONUP,
        }
        msg = msg_map.get(button.lower(), win32con.WM_LBUTTONUP)
        if targets:
            th = targets[0]
            try:
                win32gui.PostMessage(th, msg, 0, 0)
                log_debug(f"[後台引擎] 後台發送滑鼠釋放 [{button}] -> HWND {th}")
                return True
            except Exception:
                pass

        if not self._hwnd:
            try:
                flag_map = {
                    "left":   win32con.MOUSEEVENTF_LEFTUP,
                    "right":  win32con.MOUSEEVENTF_RIGHTUP,
                    "middle": win32con.MOUSEEVENTF_MIDDLEUP,
                }
                win32api.mouse_event(flag_map.get(button.lower(), win32con.MOUSEEVENTF_LEFTUP), 0, 0, 0, 0)
                return True
            except Exception:
                return False

        return False

    def send_mouse_scroll(self, direction: str, amount: int) -> bool:
        targets = self._resolve_target_hwnds()
        delta = amount * 120 if direction == "up" else -amount * 120
        wparam = (delta << 16) & 0xFFFFFFFF
        if targets:
            th = targets[0]
            try:
                win32gui.PostMessage(th, win32con.WM_MOUSEWHEEL, wparam, 0)
                return True
            except Exception:
                pass

        if not self._hwnd:
            try:
                win32api.mouse_event(win32con.MOUSEEVENTF_WHEEL, 0, 0, delta, 0)
                return True
            except Exception:
                return False

        return False

    @property
    def name(self) -> str:
        return "PostMessage 深度後台獨立通道"

    @property
    def is_available(self) -> bool:
        return True
