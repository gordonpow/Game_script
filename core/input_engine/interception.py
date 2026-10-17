"""
Interception Driver 輸入注入引擎
透過 ctypes 直接呼叫 interception.dll（核心驅動，完全後台注入）
"""
from __future__ import annotations
import ctypes
import ctypes.wintypes
import os
import time
from pathlib import Path
from typing import Optional

from core.input_engine.base import InputEngine

# ── Interception 常數 ──────────────────────────────────────────
INTERCEPTION_MAX_KEYBOARD  = 10
INTERCEPTION_MAX_MOUSE     = 10

INTERCEPTION_KEY_DOWN      = 0x00
INTERCEPTION_KEY_UP        = 0x01
INTERCEPTION_KEY_E0        = 0x02
INTERCEPTION_KEY_E1        = 0x04

INTERCEPTION_MOUSE_MOVE              = 0x0001
INTERCEPTION_MOUSE_LEFT_BUTTON_DOWN  = 0x0002
INTERCEPTION_MOUSE_LEFT_BUTTON_UP    = 0x0004
INTERCEPTION_MOUSE_RIGHT_BUTTON_DOWN = 0x0008
INTERCEPTION_MOUSE_RIGHT_BUTTON_UP   = 0x0010
INTERCEPTION_MOUSE_MIDDLE_BUTTON_DOWN= 0x0040
INTERCEPTION_MOUSE_MIDDLE_BUTTON_UP  = 0x0080
INTERCEPTION_MOUSE_WHEEL             = 0x0400
INTERCEPTION_MOUSE_HWHEEL            = 0x0800

INTERCEPTION_MOUSE_MOVE_ABSOLUTE     = 0x0001


# ── Interception C 結構體 ──────────────────────────────────────
class InterceptionKeyStroke(ctypes.Structure):
    _fields_ = [
        ("code",  ctypes.c_ushort),
        ("state", ctypes.c_ushort),
        ("information", ctypes.c_ulong),
    ]


class InterceptionMouseStroke(ctypes.Structure):
    _fields_ = [
        ("state",       ctypes.c_ushort),
        ("flags",       ctypes.c_ushort),
        ("rolling",     ctypes.c_short),
        ("x",           ctypes.c_long),
        ("y",           ctypes.c_long),
        ("information", ctypes.c_ulong),
    ]


# 鍵名 → 掃描碼映射（常用按鍵）
KEY_SCAN_CODE: dict[str, tuple[int, int]] = {
    # (scancode, flags)  flags: 0=normal, INTERCEPTION_KEY_E0=extended
    "esc": (0x01, 0), "escape": (0x01, 0),
    "f1": (0x3B, 0), "f2": (0x3C, 0), "f3": (0x3D, 0), "f4": (0x3E, 0),
    "f5": (0x3F, 0), "f6": (0x40, 0), "f7": (0x41, 0), "f8": (0x42, 0),
    "f9": (0x43, 0), "f10": (0x44, 0), "f11": (0x57, 0), "f12": (0x58, 0),
    "1": (0x02, 0), "2": (0x03, 0), "3": (0x04, 0), "4": (0x05, 0),
    "5": (0x06, 0), "6": (0x07, 0), "7": (0x08, 0), "8": (0x09, 0),
    "9": (0x0A, 0), "0": (0x0B, 0),
    "minus": (0x0C, 0), "-": (0x0C, 0),
    "equals": (0x0D, 0), "=": (0x0D, 0),
    "backspace": (0x0E, 0),
    "tab": (0x0F, 0),
    "q": (0x10, 0), "w": (0x11, 0), "e": (0x12, 0), "r": (0x13, 0),
    "t": (0x14, 0), "y": (0x15, 0), "u": (0x16, 0), "i": (0x17, 0),
    "o": (0x18, 0), "p": (0x19, 0),
    "a": (0x1E, 0), "s": (0x1F, 0), "d": (0x20, 0), "f": (0x21, 0),
    "g": (0x22, 0), "h": (0x23, 0), "j": (0x24, 0), "k": (0x25, 0),
    "l": (0x26, 0),
    "z": (0x2C, 0), "x": (0x2D, 0), "c": (0x2E, 0), "v": (0x2F, 0),
    "b": (0x30, 0), "n": (0x31, 0), "m": (0x32, 0),
    "space": (0x39, 0), " ": (0x39, 0),
    "enter": (0x1C, 0), "return": (0x1C, 0),
    "ctrl": (0x1D, 0), "control": (0x1D, 0),
    "lctrl": (0x1D, 0), "rctrl": (0x1D, INTERCEPTION_KEY_E0),
    "shift": (0x2A, 0), "lshift": (0x2A, 0), "rshift": (0x36, 0),
    "alt": (0x38, 0), "lalt": (0x38, 0), "ralt": (0x38, INTERCEPTION_KEY_E0),
    "capslock": (0x3A, 0), "caps": (0x3A, 0),
    "delete": (0x53, INTERCEPTION_KEY_E0), "del": (0x53, INTERCEPTION_KEY_E0),
    "insert": (0x52, INTERCEPTION_KEY_E0), "ins": (0x52, INTERCEPTION_KEY_E0),
    "home": (0x47, INTERCEPTION_KEY_E0),
    "end": (0x4F, INTERCEPTION_KEY_E0),
    "pageup": (0x49, INTERCEPTION_KEY_E0), "pgup": (0x49, INTERCEPTION_KEY_E0),
    "pagedown": (0x51, INTERCEPTION_KEY_E0), "pgdn": (0x51, INTERCEPTION_KEY_E0),
    "up": (0x48, INTERCEPTION_KEY_E0), "down": (0x50, INTERCEPTION_KEY_E0),
    "left": (0x4B, INTERCEPTION_KEY_E0), "right": (0x4D, INTERCEPTION_KEY_E0),
    "numpad0": (0x52, 0), "numpad1": (0x4F, 0), "numpad2": (0x50, 0),
    "numpad3": (0x51, 0), "numpad4": (0x4B, 0), "numpad5": (0x4C, 0),
    "numpad6": (0x4D, 0), "numpad7": (0x47, 0), "numpad8": (0x48, 0),
    "numpad9": (0x49, 0),
    "win": (0x5B, INTERCEPTION_KEY_E0), "lwin": (0x5B, INTERCEPTION_KEY_E0),
    "rwin": (0x5C, INTERCEPTION_KEY_E0),
    "menu": (0x5D, INTERCEPTION_KEY_E0),
    "printscreen": (0x37, INTERCEPTION_KEY_E0),
    "scrolllock": (0x46, 0),
    "pause": (0x1D, INTERCEPTION_KEY_E1),
}


class InterceptionEngine(InputEngine):
    """
    Interception Driver 輸入注入引擎
    透過 interception.dll 創建虛擬鍵鼠裝置，完全不影響實體輸入
    """

    DLL_NAME = "interception.dll"

    def __init__(self):
        self._dll: Optional[ctypes.CDLL] = None
        self._ctx: Optional[ctypes.c_void_p] = None
        self._keyboard_device: int = 1   # 預設使用裝置 1
        self._mouse_device: int = 11     # 預設使用裝置 11（mouse 從 11 開始）
        self._initialized = False

    def _find_dll(self) -> Optional[str]:
        """尋找 interception.dll 的路徑"""
        candidates = [
            Path(__file__).parent.parent.parent / "assets" / "drivers" / self.DLL_NAME,
            Path(os.environ.get("SystemRoot", "C:\\Windows")) / "System32" / self.DLL_NAME,
            Path(self.DLL_NAME),
        ]
        for path in candidates:
            if path.exists():
                return str(path)
        return None

    def initialize(self) -> bool:
        dll_path = self._find_dll()
        if not dll_path:
            print("[Interception] 找不到 interception.dll")
            return False
        try:
            self._dll = ctypes.cdll.LoadLibrary(dll_path)
            self._setup_function_signatures()
            self._ctx = self._dll.interception_create_context()
            if not self._ctx:
                print("[Interception] 建立 context 失敗，請確認驅動已安裝")
                return False
            self._initialized = True
            print("[Interception] 初始化成功")
            return True
        except Exception as e:
            print(f"[Interception] 初始化失敗: {e}")
            return False

    def _setup_function_signatures(self):
        dll = self._dll
        dll.interception_create_context.restype = ctypes.c_void_p
        dll.interception_destroy_context.argtypes = [ctypes.c_void_p]
        dll.interception_send.argtypes = [
            ctypes.c_void_p, ctypes.c_int,
            ctypes.c_void_p, ctypes.c_uint
        ]
        dll.interception_send.restype = ctypes.c_int

    def shutdown(self) -> None:
        if self._ctx and self._dll:
            try:
                self._dll.interception_destroy_context(self._ctx)
            except Exception:
                pass
        self._ctx = None
        self._initialized = False

    def _send_key_stroke(self, code: int, state: int, flags: int = 0):
        if not self._initialized:
            return False
        stroke = InterceptionKeyStroke(code=code, state=state | flags, information=0)
        self._dll.interception_send(
            self._ctx, self._keyboard_device,
            ctypes.byref(stroke), 1
        )
        return True

    def _send_mouse_stroke(self, state: int, flags: int = 0,
                           rolling: int = 0, x: int = 0, y: int = 0):
        if not self._initialized:
            return False
        stroke = InterceptionMouseStroke(
            state=state, flags=flags,
            rolling=rolling, x=x, y=y, information=0
        )
        self._dll.interception_send(
            self._ctx, self._mouse_device,
            ctypes.byref(stroke), 1
        )
        return True

    def send_key_down(self, key: str) -> bool:
        key = key.lower()
        sc_info = KEY_SCAN_CODE.get(key)
        if sc_info is None:
            print(f"[Interception] 未知按鍵: {key}")
            return False
        sc, flags = sc_info
        return self._send_key_stroke(sc, INTERCEPTION_KEY_DOWN, flags)

    def send_key_up(self, key: str) -> bool:
        key = key.lower()
        sc_info = KEY_SCAN_CODE.get(key)
        if sc_info is None:
            return False
        sc, flags = sc_info
        return self._send_key_stroke(sc, INTERCEPTION_KEY_UP, flags)

    def send_mouse_move(self, abs_x: int, abs_y: int) -> bool:
        # 轉換為 Interception 的 0~65535 絕對座標
        import ctypes
        screen_w = ctypes.windll.user32.GetSystemMetrics(0)
        screen_h = ctypes.windll.user32.GetSystemMetrics(1)
        norm_x = int(abs_x * 65535 / screen_w)
        norm_y = int(abs_y * 65535 / screen_h)
        return self._send_mouse_stroke(
            state=INTERCEPTION_MOUSE_MOVE,
            flags=INTERCEPTION_MOUSE_MOVE_ABSOLUTE,
            x=norm_x, y=norm_y
        )

    def send_mouse_button_down(self, button: str) -> bool:
        states = {
            "left":   INTERCEPTION_MOUSE_LEFT_BUTTON_DOWN,
            "right":  INTERCEPTION_MOUSE_RIGHT_BUTTON_DOWN,
            "middle": INTERCEPTION_MOUSE_MIDDLE_BUTTON_DOWN,
        }
        state = states.get(button.lower(), INTERCEPTION_MOUSE_LEFT_BUTTON_DOWN)
        return self._send_mouse_stroke(state=state)

    def send_mouse_button_up(self, button: str) -> bool:
        states = {
            "left":   INTERCEPTION_MOUSE_LEFT_BUTTON_UP,
            "right":  INTERCEPTION_MOUSE_RIGHT_BUTTON_UP,
            "middle": INTERCEPTION_MOUSE_MIDDLE_BUTTON_UP,
        }
        state = states.get(button.lower(), INTERCEPTION_MOUSE_LEFT_BUTTON_UP)
        return self._send_mouse_stroke(state=state)

    def send_mouse_scroll(self, direction: str, amount: int) -> bool:
        if direction in ("up", "down"):
            rolling = amount * 120 if direction == "up" else -amount * 120
            return self._send_mouse_stroke(
                state=INTERCEPTION_MOUSE_WHEEL, rolling=rolling
            )
        else:
            rolling = amount * 120 if direction == "right" else -amount * 120
            return self._send_mouse_stroke(
                state=INTERCEPTION_MOUSE_HWHEEL, rolling=rolling
            )

    @property
    def name(self) -> str:
        return "Interception Driver"

    @property
    def is_available(self) -> bool:
        return self._find_dll() is not None
