"""
Profile 遊戲設定檔資料模型
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
import uuid

from models.macro import Macro


class InputMode:
    INTERCEPTION  = "interception"   # 核心驅動：Interception Driver
    POST_MESSAGE  = "postmessage"    # 後台通道：PostMessage（純後台，不干擾前台）
    SEND_INPUT    = "sendinput"       # 前台相容：SendInput（高相容性，需維持前台焦點）


class DeviceMode:
    KEYBOARD  = "keyboard"
    GAMEPAD   = "gamepad"
    BOTH      = "both"


@dataclass
class HotkeyConfig:
    """熱鍵設定"""
    start_pause: str = "Ctrl+F1"     # 開始/暫停執行（必填）
    record_toggle: str = "Ctrl+F2"   # 開始/停止錄製（必填）
    stop: str = "F12"                # 強制停止執行（選填）

    def is_valid(self) -> bool:
        return bool(self.start_pause.strip())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "start_pause": self.start_pause,
            "record_toggle": self.record_toggle,
            "stop": self.stop,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "HotkeyConfig":
        return cls(
            start_pause=d.get("start_pause", "Ctrl+F1"),
            record_toggle=d.get("record_toggle", "Ctrl+F2"),
            stop=d.get("stop", "F12"),
        )


@dataclass
class Profile:
    """
    遊戲設定檔：包含目標視窗、輸入模式、熱鍵設定與所有巨集
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = "新設定檔"
    target_window_title: str = ""       # 目標視窗標題（部分比對）
    target_window_exe: str = ""         # 目標程序名稱（可選）
    target_hwnd: int = 0                # 執行時動態設定，不存檔
    input_mode: str = InputMode.INTERCEPTION
    device_mode: str = DeviceMode.KEYBOARD
    hotkeys: HotkeyConfig = field(default_factory=HotkeyConfig)
    macros: List[Macro] = field(default_factory=list)
    icon_path: str = ""

    @property
    def target_window(self) -> Optional[Any]:
        """相容 WindowInfo 存取，支援動態自動尋找最新有效 HWND"""
        import win32gui
        # 若已有快取且視窗依然存活，直接回傳
        if hasattr(self, "_cached_window_info") and self._cached_window_info is not None:
            if getattr(self._cached_window_info, "hwnd", 0) and win32gui.IsWindow(self._cached_window_info.hwnd):
                return self._cached_window_info

        # 若 HWND 失效或為 0，嘗試依據標題或 exe 自動尋找正在運行的視窗
        if self.target_window_title:
            try:
                from core.window_manager import WindowManager
                found = WindowManager.find_window_by_title(self.target_window_title)
                if found and win32gui.IsWindow(found.hwnd):
                    self.target_hwnd = found.hwnd
                    self._cached_window_info = found
                    return found
            except Exception:
                pass

        if self.target_hwnd and win32gui.IsWindow(self.target_hwnd):
            from core.window_manager import WindowInfo
            return WindowInfo(
                hwnd=self.target_hwnd,
                title=self.target_window_title,
                exe_name=self.target_window_exe,
                rect=(0, 0, 1920, 1080)
            )
        return None

    @target_window.setter
    def target_window(self, val: Any):
        self._cached_window_info = val
        if val is not None:
            self.target_hwnd = getattr(val, "hwnd", 0)
            self.target_window_title = getattr(val, "title", "")
            self.target_window_exe = getattr(val, "process_name", "") or getattr(val, "exe_name", "")
        else:
            self.target_hwnd = 0
            self.target_window_title = ""
            self.target_window_exe = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "target_hwnd": self.target_hwnd,
            "target_window_title": self.target_window_title,
            "target_window_exe": self.target_window_exe,
            "input_mode": self.input_mode,
            "device_mode": self.device_mode,
            "hotkeys": self.hotkeys.to_dict(),
            "macros": [m.to_dict() for m in self.macros],
            "icon_path": self.icon_path,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Profile":
        return cls(
            id=d.get("id", str(uuid.uuid4())),
            name=d.get("name", "新設定檔"),
            target_hwnd=d.get("target_hwnd", 0),
            target_window_title=d.get("target_window_title", ""),
            target_window_exe=d.get("target_window_exe", ""),
            input_mode=d.get("input_mode", InputMode.INTERCEPTION),
            device_mode=d.get("device_mode", DeviceMode.KEYBOARD),
            hotkeys=HotkeyConfig.from_dict(d.get("hotkeys", {})),
            macros=[Macro.from_dict(m) for m in d.get("macros", [])],
            icon_path=d.get("icon_path", ""),
        )
