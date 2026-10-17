"""
視窗管理 - 視窗偵測、座標轉換、準星吸附選取
"""
from __future__ import annotations
import ctypes
import ctypes.wintypes
from dataclasses import dataclass
from typing import List, Optional, Tuple
import win32api
import win32con
import win32gui
import win32process


@dataclass
class WindowInfo:
    """視窗資訊"""
    hwnd: int
    title: str
    exe_name: str
    rect: Tuple[int, int, int, int]  # (left, top, right, bottom)
    pid: int = 0


    @property
    def width(self) -> int:
        return self.rect[2] - self.rect[0]

    @property
    def height(self) -> int:
        return self.rect[3] - self.rect[1]

    @property
    def left(self) -> int:
        return self.rect[0]

    @property
    def top(self) -> int:
        return self.rect[1]

    @property
    def process_name(self) -> str:
        return self.exe_name

    def __str__(self) -> str:
        return f"{self.exe_name} — {self.title} [{self.width}x{self.height}]"


class WindowManager:
    """視窗管理器"""

    @staticmethod
    def enumerate_windows() -> List[WindowInfo]:
        """枚舉所有可見的頂層視窗別名"""
        return WindowManager.get_all_windows()

    @staticmethod
    def get_all_windows() -> List[WindowInfo]:
        """枚舉所有可見的頂層視窗"""
        windows: List[WindowInfo] = []

        def enum_callback(hwnd: int, _):
            if not win32gui.IsWindowVisible(hwnd):
                return True
            title = win32gui.GetWindowText(hwnd)
            if not title:
                return True
            try:
                _, pid = win32process.GetWindowThreadProcessId(hwnd)
                handle = win32api.OpenProcess(
                    win32con.PROCESS_QUERY_INFORMATION | win32con.PROCESS_VM_READ,
                    False, pid
                )
                exe_path = win32process.GetModuleFileNameEx(handle, 0)
                exe_name = exe_path.split("\\")[-1]
                win32api.CloseHandle(handle)
            except Exception:
                exe_name = "unknown.exe"
            try:
                rect = win32gui.GetWindowRect(hwnd)
            except Exception:
                return True
            w = rect[2] - rect[0]
            h = rect[3] - rect[1]
            if w < 50 or h < 50:
                return True
            windows.append(WindowInfo(
                hwnd=hwnd,
                title=title,
                exe_name=exe_name,
                rect=rect,
                pid=pid,
            ))
            return True

        win32gui.EnumWindows(enum_callback, None)
        return sorted(windows, key=lambda w: w.title.lower())

    @staticmethod
    def get_window_by_hwnd(hwnd: int) -> Optional[WindowInfo]:
        """根據 HWND 取得視窗資訊（即時更新 rect）"""
        try:
            title = win32gui.GetWindowText(hwnd)
            rect = win32gui.GetWindowRect(hwnd)
            pid = 0
            try:
                _, pid = win32process.GetWindowThreadProcessId(hwnd)
                handle = win32api.OpenProcess(
                    win32con.PROCESS_QUERY_INFORMATION | win32con.PROCESS_VM_READ,
                    False, pid
                )
                exe_path = win32process.GetModuleFileNameEx(handle, 0)
                exe_name = exe_path.split("\\")[-1]
                win32api.CloseHandle(handle)
            except Exception:
                exe_name = "unknown.exe"
            return WindowInfo(hwnd=hwnd, title=title, exe_name=exe_name, rect=rect, pid=pid)

        except Exception:
            return None

    @staticmethod
    def find_window_by_title(title_part: str) -> Optional[WindowInfo]:
        """根據標題部分比對找視窗"""
        for win in WindowManager.get_all_windows():
            if title_part.lower() in win.title.lower():
                return win
        return None

    @staticmethod
    def get_window_rect(hwnd: int) -> Optional[Tuple[int, int, int, int]]:
        """即時取得視窗 Rect"""
        try:
            return win32gui.GetWindowRect(hwnd)
        except Exception:
            return None

    @staticmethod
    def is_window_valid(hwnd: int) -> bool:
        """檢查視窗是否仍然有效"""
        try:
            return win32gui.IsWindow(hwnd) and win32gui.IsWindowVisible(hwnd)
        except Exception:
            return False

    @staticmethod
    def get_foreground_window() -> Optional[WindowInfo]:
        """取得當前系統前台焦點視窗"""
        try:
            hwnd = win32gui.GetForegroundWindow()
            if hwnd and WindowManager.is_window_valid(hwnd):
                return WindowManager.get_window_by_hwnd(hwnd)
        except Exception:
            pass
        return None

    # ── 座標轉換 ──────────────────────────────────────────────
    @staticmethod
    def abs_to_rel(abs_x: int, abs_y: int, hwnd: int) -> Optional[Tuple[float, float]]:
        """
        絕對螢幕座標 → 相對視窗比例座標 (0.0~1.0)
        用於錄製時儲存
        """
        rect = WindowManager.get_window_rect(hwnd)
        if rect is None:
            return None
        left, top, right, bottom = rect
        w = right - left
        h = bottom - top
        if w <= 0 or h <= 0:
            return None
        rel_x = (abs_x - left) / w
        rel_y = (abs_y - top) / h
        return (rel_x, rel_y)

    @staticmethod
    def rel_to_abs(rel_x: float, rel_y: float, hwnd: int) -> Optional[Tuple[int, int]]:
        """
        相對視窗比例座標 → 絕對螢幕座標
        用於回放時換算（即時偵測視窗位置）
        """
        rect = WindowManager.get_window_rect(hwnd)
        if rect is None:
            return None
        left, top, right, bottom = rect
        w = right - left
        h = bottom - top
        abs_x = int(left + rel_x * w)
        abs_y = int(top + rel_y * h)
        return (abs_x, abs_y)

    # ── 準星吸附視窗選取 ──────────────────────────────────────
    @staticmethod
    def start_crosshair_picker(callback) -> None:
        """
        啟動準星吸附視窗選取模式
        使用者滑鼠移動時高亮目標視窗，點擊左鍵確認選取
        callback(hwnd: int) 在選取後呼叫
        在 Thread 中執行避免阻塞 UI
        """
        import threading

        def _picker_thread():
            import time
            last_hwnd = 0
            print("[WindowPicker] 準星吸附模式啟動，左鍵點擊選取視窗...")
            try:
                import pynput.mouse as pm
                selected = [None]
                done = [False]

                def on_move(x, y):
                    nonlocal last_hwnd
                    hwnd = win32gui.WindowFromPoint((x, y))
                    # 取得頂層父視窗
                    hwnd = win32gui.GetAncestor(hwnd, win32con.GA_ROOT)
                    if hwnd != last_hwnd and hwnd:
                        last_hwnd = hwnd
                        title = win32gui.GetWindowText(hwnd)
                        print(f"[WindowPicker] 指向: {title} (HWND={hwnd})")

                def on_click(x, y, button, pressed):
                    if pressed and button == pm.Button.left:
                        hwnd = win32gui.WindowFromPoint((x, y))
                        hwnd = win32gui.GetAncestor(hwnd, win32con.GA_ROOT)
                        selected[0] = hwnd
                        done[0] = True
                        return False  # 停止監聽

                listener = pm.Listener(on_move=on_move, on_click=on_click)
                listener.start()
                while not done[0]:
                    time.sleep(0.05)
                listener.stop()
                if selected[0]:
                    callback(selected[0])
            except Exception as e:
                print(f"[WindowPicker] 錯誤: {e}")

        threading.Thread(target=_picker_thread, daemon=True).start()
