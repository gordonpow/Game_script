"""
驅動安裝 / 偵測工具
負責偵測 Interception Driver 與 ViGEm Bus 是否已安裝
並提供一鍵安裝功能
"""
from __future__ import annotations
import os
import subprocess
import winreg
from pathlib import Path
from typing import Tuple


def _check_registry_key(hive, key_path: str) -> bool:
    """檢查 Windows 登錄檔中是否存在某個鍵"""
    try:
        with winreg.OpenKey(hive, key_path):
            return True
    except FileNotFoundError:
        return False


def is_interception_installed() -> bool:
    """
    偵測 Interception Driver 是否真正已安裝並在核心中運作
    藉由嘗試建立 context 來實測，避免僅有 DLL 卻無核心驅動的假陽性
    """
    import ctypes
    dll_paths = [
        Path(os.environ.get("SystemRoot", "C:\\Windows")) / "System32" / "interception.dll",
        Path(__file__).parent.parent / "assets" / "drivers" / "interception.dll",
    ]
    target_dll = None
    for p in dll_paths:
        if p.exists():
            target_dll = str(p)
            break

    if not target_dll:
        return False

    try:
        dll = ctypes.cdll.LoadLibrary(target_dll)
        dll.interception_create_context.restype = ctypes.c_void_p
        dll.interception_destroy_context.argtypes = [ctypes.c_void_p]
        ctx = dll.interception_create_context()
        if ctx:
            dll.interception_destroy_context(ctx)
            return True
        return False
    except Exception:
        return False


def is_vigem_installed() -> bool:
    """偵測 ViGEm Bus 是否已安裝"""
    # 方法1: 檢查服務
    if _check_registry_key(
        winreg.HKEY_LOCAL_MACHINE,
        r"SYSTEM\CurrentControlSet\Services\ViGEmBus"
    ):
        return True

    # 方法2: 檢查安裝記錄
    for sub in [
        r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall",
        r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall",
    ]:
        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, sub) as key:
                i = 0
                while True:
                    try:
                        sub_key_name = winreg.EnumKey(key, i)
                        with winreg.OpenKey(key, sub_key_name) as sub_key:
                            try:
                                name, _ = winreg.QueryValueEx(sub_key, "DisplayName")
                                if "ViGEm" in str(name) or "vigem" in str(name).lower():
                                    return True
                            except FileNotFoundError:
                                pass
                        i += 1
                    except OSError:
                        break
        except Exception:
            pass

    # 方法3: 嘗試 import vgamepad
    try:
        import vgamepad
        return True
    except Exception:
        return False


def get_drivers_dir() -> Path:
    """取得內嵌驅動目錄"""
    return Path(__file__).parent.parent / "assets" / "drivers"


def _run_as_admin(exe_path: str, params: str) -> Tuple[bool, str]:
    """以管理員權限 (UAC runas) 執行安裝檔並等待完成"""
    import ctypes
    from ctypes import wintypes
    
    # 建立 ShellExecuteEx 所需的結構
    class SHELLEXECUTEINFO(ctypes.Structure):
        _fields_ = [
            ("cbSize", wintypes.DWORD),
            ("fMask", ctypes.c_ulong),
            ("hwnd", wintypes.HWND),
            ("lpVerb", wintypes.LPCWSTR),
            ("lpFile", wintypes.LPCWSTR),
            ("lpParameters", wintypes.LPCWSTR),
            ("lpDirectory", wintypes.LPCWSTR),
            ("nShow", ctypes.c_int),
            ("hInstApp", wintypes.HINSTANCE),
            ("lpIDList", ctypes.c_void_p),
            ("lpClass", wintypes.LPCWSTR),
            ("hkeyClass", wintypes.HKEY),
            ("dwHotKey", wintypes.DWORD),
            ("hIconOrMonitor", wintypes.HANDLE),
            ("hProcess", wintypes.HANDLE),
        ]

    SEE_MASK_NOCLOSEPROCESS = 0x00000040
    sei = SHELLEXECUTEINFO()
    sei.cbSize = ctypes.sizeof(SHELLEXECUTEINFO)
    sei.fMask = SEE_MASK_NOCLOSEPROCESS
    sei.hwnd = None
    sei.lpVerb = "runas"
    sei.lpFile = exe_path
    sei.lpParameters = params
    sei.lpDirectory = os.path.dirname(exe_path)
    sei.nShow = 1  # SW_SHOWNORMAL

    if not ctypes.windll.shell32.ShellExecuteExW(ctypes.byref(sei)):
        err = ctypes.windll.kernel32.GetLastError()
        if err == 1223:  # ERROR_CANCELLED (使用者取消了 UAC 提示)
            return False, "使用者取消了管理員授權"
        return False, f"啟動失敗 (WinError {err})"

    if sei.hProcess:
        # 等待安裝程式執行完成（最長 180 秒）
        ctypes.windll.kernel32.WaitForSingleObject(sei.hProcess, 180000)
        exit_code = wintypes.DWORD()
        ctypes.windll.kernel32.GetExitCodeProcess(sei.hProcess, ctypes.byref(exit_code))
        ctypes.windll.kernel32.CloseHandle(sei.hProcess)
        code = exit_code.value
        if code in (0, 3010):
            return True, "安裝成功" + ("（請重開機以生效）" if code == 3010 else "")
        return True, f"安裝程序已結束 (Exit Code {code})"

    return True, "安裝程式已啟動"


def install_interception(parent_hwnd=None) -> Tuple[bool, str]:
    """安裝 Interception Driver"""
    drivers_dir = get_drivers_dir()
    installer = drivers_dir / "interception_install.exe"

    if not installer.exists():
        return False, f"找不到 Interception 安裝程式: {installer}"

    try:
        ok, msg = _run_as_admin(str(installer), "/install")
        if ok:
            return True, "Interception Driver 安裝已執行！請重新開機使驅動生效。"
        return False, msg
    except Exception as e:
        return False, f"安裝異常: {e}"


def install_vigem(parent_hwnd=None) -> Tuple[bool, str]:
    """安裝 ViGEm Bus Driver"""
    drivers_dir = get_drivers_dir()
    for name in ["ViGEmBus_Setup.exe", "ViGEmBus_Setup.msi", "ViGEmBus.msi"]:
        installer = drivers_dir / name
        if installer.exists():
            try:
                ok, msg = _run_as_admin(str(installer), "/passive /norestart" if installer.suffix == ".exe" else "/quiet /norestart")
                if ok:
                    return True, "ViGEm Bus 安裝已執行完成！"
                return False, msg
            except Exception as e:
                return False, f"安裝異常: {e}"

    return False, "找不到 ViGEm Bus 安裝程式"


def check_all_drivers() -> dict:
    """
    檢查所有驅動狀態
    回傳 {'interception': bool, 'vigem': bool}
    """
    return {
        "interception": is_interception_installed(),
        "vigem": is_vigem_installed(),
    }
