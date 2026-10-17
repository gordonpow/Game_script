"""
SendInput 前台相容輸入引擎
使用 Win32 原生 SendInput / keybd_event 注入指令
相容性 100%（適用於所有遊戲、DirectX 全螢幕、Chrome 鍵盤測試網頁等）
注意：此模式需要目標視窗處於前台焦點
"""
from __future__ import annotations
import time
from typing import Optional

import win32api
import win32con
import win32gui

from core.input_engine.base import InputEngine
from core.logger import log_info, log_debug, log_warn, log_error
from core.input_engine.postmessage import VK_MAP


class SendInputEngine(InputEngine):
    """前台相容輸入引擎（DirectX / Chrome 全相容）"""

    def __init__(self, hwnd: int = 0):
        self._hwnd = hwnd
        self._initialized = False

    def set_target_hwnd(self, hwnd: int):
        self._hwnd = hwnd

    def initialize(self) -> bool:
        self._initialized = True
        log_info(f"[前台引擎] SendInput 引擎初始化就緒 (目標 HWND: {self._hwnd})")
        return True

    def shutdown(self) -> None:
        self._initialized = False

    def _ensure_foreground(self):
        """若有指定視窗且非焦點，嘗試將其置於前台以確保輸入生效"""
        if self._hwnd and win32gui.IsWindow(self._hwnd):
            cur_fg = win32gui.GetForegroundWindow()
            if cur_fg != self._hwnd:
                try:
                    win32gui.SetForegroundWindow(self._hwnd)
                except Exception:
                    pass

    def send_key_down(self, key: str) -> bool:
        vk = VK_MAP.get(key.lower())
        if vk is None:
            return False
        try:
            self._ensure_foreground()
            scan_code = win32api.MapVirtualKey(vk, 0)
            win32api.keybd_event(vk, scan_code, 0, 0)
            log_debug(f"[前台引擎] SendInput KEY_DOWN [{key.upper()}] (VK: 0x{vk:02X})")
            return True
        except Exception as e:
            log_error(f"[前台引擎] send_key_down 失敗: {e}")
            return False

    def send_key_up(self, key: str) -> bool:
        vk = VK_MAP.get(key.lower())
        if vk is None:
            return False
        try:
            scan_code = win32api.MapVirtualKey(vk, 0)
            win32api.keybd_event(vk, scan_code, win32con.KEYEVENTF_KEYUP, 0)
            log_debug(f"[前台引擎] SendInput KEY_UP [{key.upper()}] (VK: 0x{vk:02X})")
            return True
        except Exception as e:
            log_error(f"[前台引擎] send_key_up 失敗: {e}")
            return False

    def send_mouse_move(self, abs_x: int, abs_y: int) -> bool:
        try:
            win32api.SetCursorPos((abs_x, abs_y))
            return True
        except Exception:
            return False

    def send_mouse_button_down(self, button: str) -> bool:
        flag_map = {
            "left":   win32con.MOUSEEVENTF_LEFTDOWN,
            "right":  win32con.MOUSEEVENTF_RIGHTDOWN,
            "middle": win32con.MOUSEEVENTF_MIDDLEDOWN,
        }
        try:
            self._ensure_foreground()
            win32api.mouse_event(flag_map.get(button.lower(), win32con.MOUSEEVENTF_LEFTDOWN), 0, 0, 0, 0)
            return True
        except Exception:
            return False

    def send_mouse_button_up(self, button: str) -> bool:
        flag_map = {
            "left":   win32con.MOUSEEVENTF_LEFTUP,
            "right":  win32con.MOUSEEVENTF_RIGHTUP,
            "middle": win32con.MOUSEEVENTF_MIDDLEUP,
        }
        try:
            win32api.mouse_event(flag_map.get(button.lower(), win32con.MOUSEEVENTF_LEFTUP), 0, 0, 0, 0)
            return True
        except Exception:
            return False

    def send_mouse_scroll(self, direction: str, amount: int) -> bool:
        delta = amount * 120 if direction == "up" else -amount * 120
        try:
            win32api.mouse_event(win32con.MOUSEEVENTF_WHEEL, 0, 0, delta, 0)
            return True
        except Exception:
            return False

    @property
    def name(self) -> str:
        return "SendInput 前台相容通道"

    @property
    def is_available(self) -> bool:
        return True
