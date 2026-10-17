"""
ViGEm 虛擬搖桿引擎
透過 vgamepad 套件建立並控制虛擬 Xbox 360 控制器
提供按鍵按下/釋放、板機鍵推壓、蘑菇頭軸推動等功能
支援程式啟動時預先激活，讓遊戲與瀏覽器在開啟軟體瞬間即識別手把
"""
from __future__ import annotations
import time
import logging
from typing import Optional

from core.logger import log_info, log_warn, log_debug, log_error

logger = logging.getLogger(__name__)

# 嘗試載入 vgamepad
_VGAMEPAD_AVAILABLE = False
try:
    import vgamepad as vg
    _VGAMEPAD_AVAILABLE = True
except ImportError:
    vg = None


class ViGEmEngine:
    """
    ViGEm 虛擬搖桿控制引擎 (Xbox 360 Controller)
    """

    def __init__(self):
        self._pad: Optional[object] = None
        self._initialized = False
        self._BUTTON_MAP = {}

        if _VGAMEPAD_AVAILABLE and vg:
            self._BUTTON_MAP = {
                "A": vg.XUSB_BUTTON.XUSB_GAMEPAD_A,
                "B": vg.XUSB_BUTTON.XUSB_GAMEPAD_B,
                "X": vg.XUSB_BUTTON.XUSB_GAMEPAD_X,
                "Y": vg.XUSB_BUTTON.XUSB_GAMEPAD_Y,
                "LB": vg.XUSB_BUTTON.XUSB_GAMEPAD_LEFT_SHOULDER,
                "RB": vg.XUSB_BUTTON.XUSB_GAMEPAD_RIGHT_SHOULDER,
                "START": vg.XUSB_BUTTON.XUSB_GAMEPAD_START,
                "BACK": vg.XUSB_BUTTON.XUSB_GAMEPAD_BACK,
                "LS": vg.XUSB_BUTTON.XUSB_GAMEPAD_LEFT_THUMB,
                "RS": vg.XUSB_BUTTON.XUSB_GAMEPAD_RIGHT_THUMB,
                "DPAD_UP": vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_UP,
                "DPAD_DOWN": vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_DOWN,
                "DPAD_LEFT": vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_LEFT,
                "DPAD_RIGHT": vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_RIGHT,
            }

    @property
    def is_available(self) -> bool:
        """檢查 vgamepad 套件與驅動是否可用"""
        return _VGAMEPAD_AVAILABLE

    @property
    def is_connected(self) -> bool:
        """檢查虛擬手把是否處於連線激活狀態"""
        return self._initialized and self._pad is not None

    def connect(self, wake_up: bool = True) -> bool:
        """
        建立虛擬搖桿連線
        wake_up: 是否發送微小按鍵訊號喚醒 Windows Gamepad 系統與瀏覽器 API
        """
        if not _VGAMEPAD_AVAILABLE or vg is None:
            log_warn("⚠️ [手把引擎] vgamepad 模組或 ViGEmBus 驅動不可用，無法啟動虛擬手把。")
            return False

        if self.is_connected:
            return True

        try:
            self._pad = vg.VX360Gamepad()
            self._initialized = True
            log_info("🎮 [手把引擎] 虛擬 Xbox 360 手把已成功插上 Windows 系統！")

            if wake_up:
                # 傳送 20ms 微小按鍵喚醒訊號，觸發 Windows 與 Chrome/Edge 的 gamepadconnected 事件
                try:
                    self._pad.press_button(button=vg.XUSB_BUTTON.XUSB_GAMEPAD_A)
                    self._pad.update()
                    time.sleep(0.02)
                    self._pad.release_button(button=vg.XUSB_BUTTON.XUSB_GAMEPAD_A)
                    self._pad.update()
                    log_info("✨ [手把引擎] 已向系統發送手把激活訊號 (網頁與遊戲已即時識別 Gamepad 1)")
                except Exception as e_wake:
                    log_debug(f"[手把引擎] 激活訊號發送忽略: {e_wake}")

            return True
        except Exception as e:
            log_warn(f"⚠️ [手把引擎] 建立虛擬搖桿失敗: {e} (若尚未安裝驅動請先至頂層工具列安裝)")
            self._initialized = False
            self._pad = None
            return False

    def disconnect(self):
        """斷開虛擬搖桿"""
        if self._pad is not None:
            try:
                self.reset()
                del self._pad
            except Exception:
                pass
            self._pad = None
            self._initialized = False
            log_info("🎮 [手把引擎] 虛擬 Xbox 360 手把已離線拔除。")

    def press_button(self, button_name: str):
        """按下按鍵"""
        if not self._initialized or self._pad is None:
            return

        b_upper = str(button_name).upper().strip()
        if b_upper == "LT":
            self._pad.left_trigger_float(value_float=1.0)
            self._pad.update()
        elif b_upper == "RT":
            self._pad.right_trigger_float(value_float=1.0)
            self._pad.update()
        elif b_upper in self._BUTTON_MAP:
            self._pad.press_button(button=self._BUTTON_MAP[b_upper])
            self._pad.update()

    def release_button(self, button_name: str):
        """釋放按鍵"""
        if not self._initialized or self._pad is None:
            return

        b_upper = str(button_name).upper().strip()
        if b_upper == "LT":
            self._pad.left_trigger_float(value_float=0.0)
            self._pad.update()
        elif b_upper == "RT":
            self._pad.right_trigger_float(value_float=0.0)
            self._pad.update()
        elif b_upper in self._BUTTON_MAP:
            self._pad.release_button(button=self._BUTTON_MAP[b_upper])
            self._pad.update()

    def click_button(self, button_name: str, hold_ms: int = 50):
        """點擊按鍵（按下後保持 hold_ms 再釋放）"""
        self.press_button(button_name)
        if hold_ms > 0:
            time.sleep(hold_ms / 1000.0)
        self.release_button(button_name)

    def set_axis(self, axis_name: str, value: float):
        """
        推動蘑菇頭軸 (-1.0 ~ 1.0)
        axis_name: 'LX', 'LY', 'RX', 'RY'
        """
        if not self._initialized or self._pad is None:
            return

        clamped = max(-1.0, min(1.0, float(value)))
        a_upper = str(axis_name).upper().strip()

        if a_upper == "LX":
            self._pad.left_joystick_float(x_value_float=clamped, y_value_float=0.0)
        elif a_upper == "LY":
            self._pad.left_joystick_float(x_value_float=0.0, y_value_float=clamped)
        elif a_upper == "RX":
            self._pad.right_joystick_float(x_value_float=clamped, y_value_float=0.0)
        elif a_upper == "RY":
            self._pad.right_joystick_float(x_value_float=0.0, y_value_float=clamped)

        self._pad.update()

    def reset(self):
        """重設所有按鍵與軸狀態到中心位"""
        if not self._initialized or self._pad is None:
            return
        try:
            self._pad.reset()
            self._pad.update()
        except Exception:
            pass


# ── 全域單例手把引擎 ───────────────────────────────────────────
_global_vigem_engine: Optional[ViGEmEngine] = None


def get_vigem_engine() -> ViGEmEngine:
    """取得或建立全域唯一的 ViGEm 虛擬手把引擎"""
    global _global_vigem_engine
    if _global_vigem_engine is None:
        _global_vigem_engine = ViGEmEngine()
    return _global_vigem_engine
