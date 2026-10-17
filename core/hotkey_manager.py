"""
全域熱鍵管理器
支援組合鍵（如 Ctrl+F1）、全域監聽（前後台皆有效）
"""
from __future__ import annotations
import threading
from typing import Callable, Dict, Optional, Set, Tuple


class HotkeyManager:
    """
    全域熱鍵管理器
    使用 keyboard 函式庫實作全域熱鍵（不依賴視窗焦點）
    """

    def __init__(self):
        self._hotkeys: Dict[str, Callable] = {}  # hotkey_str → callback
        self._registered_ids: Dict[str, int] = {}  # hotkey_str → keyboard hook id
        self._enabled: bool = True
        self._lock = threading.Lock()

    def start(self):
        """啟動或啟用熱鍵監聽"""
        self._enabled = True

    def register(self, hotkey_str: str, callback: Callable, suppress: bool = False) -> bool:
        """
        註冊熱鍵
        hotkey_str: 熱鍵字串，如 "ctrl+f1", "alt+f5", "f7"
        callback: 觸發時呼叫的函數
        suppress: 是否抑制原始按鍵傳遞（錄製時需要）
        """
        if not hotkey_str:
            return False
        hotkey_str = hotkey_str.lower().strip()
        self.unregister(hotkey_str)

        try:
            import keyboard
            hook_id = keyboard.add_hotkey(
                hotkey_str,
                lambda: self._dispatch(hotkey_str),
                suppress=suppress,
                trigger_on_release=False,
            )
            with self._lock:
                self._hotkeys[hotkey_str] = callback
                self._registered_ids[hotkey_str] = hook_id
            print(f"[Hotkey] 已註冊: {hotkey_str}")
            return True
        except Exception as e:
            print(f"[Hotkey] 註冊失敗 [{hotkey_str}]: {e}")
            return False

    def unregister(self, hotkey_str: str):
        hotkey_str = hotkey_str.lower().strip()
        with self._lock:
            if hotkey_str in self._registered_ids:
                try:
                    import keyboard
                    keyboard.remove_hotkey(self._registered_ids[hotkey_str])
                except Exception:
                    pass
                del self._registered_ids[hotkey_str]
            self._hotkeys.pop(hotkey_str, None)

    def unregister_all(self):
        """取消所有已註冊的熱鍵"""
        with self._lock:
            keys = list(self._registered_ids.keys())
        for k in keys:
            self.unregister(k)

    def clear(self):
        """清空所有熱鍵"""
        self.unregister_all()

    def stop(self):
        """停止並清空熱鍵"""
        self.unregister_all()
        self._enabled = False

    def enable(self):
        self._enabled = True

    def disable(self):
        self._enabled = False

    def _dispatch(self, hotkey_str: str):
        if not self._enabled:
            return
        with self._lock:
            cb = self._hotkeys.get(hotkey_str)
        if cb:
            try:
                cb()
            except Exception as e:
                print(f"[Hotkey] 回呼錯誤 [{hotkey_str}]: {e}")

    @staticmethod
    def parse_hotkey(hotkey_str: str) -> Tuple[Set[str], str]:
        """
        解析熱鍵字串為修飾鍵集合和主鍵
        例如 "ctrl+f1" → ({"ctrl"}, "f1")
        """
        parts = [p.strip().lower() for p in hotkey_str.split("+")]
        modifiers = {"ctrl", "shift", "alt", "win"}
        mods = set()
        main_key = ""
        for p in parts:
            if p in modifiers:
                mods.add(p)
            else:
                main_key = p
        return mods, main_key

    @staticmethod
    def normalize_hotkey(hotkey_str: str) -> str:
        """標準化熱鍵字串"""
        mods, main = HotkeyManager.parse_hotkey(hotkey_str)
        parts = sorted(mods) + ([main] if main else [])
        return "+".join(parts)

    @staticmethod
    def validate_hotkey(hotkey_str: str) -> bool:
        """驗證熱鍵字串是否有效"""
        if not hotkey_str:
            return False
        _, main = HotkeyManager.parse_hotkey(hotkey_str)
        return bool(main)

    @staticmethod
    def check_conflicts(hotkey1: str, hotkey2: str) -> bool:
        """檢查兩個熱鍵是否衝突"""
        if not hotkey1 or not hotkey2:
            return False
        n1 = HotkeyManager.normalize_hotkey(hotkey1)
        n2 = HotkeyManager.normalize_hotkey(hotkey2)
        return n1 == n2
