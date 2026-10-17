"""
輸入引擎抽象基底類別
所有輸入注入方案都繼承此類別
"""
from abc import ABC, abstractmethod
from typing import Tuple


class InputEngine(ABC):
    """輸入注入引擎抽象基底"""

    @abstractmethod
    def initialize(self) -> bool:
        """初始化引擎，回傳是否成功"""
        ...

    @abstractmethod
    def shutdown(self) -> None:
        """關閉引擎"""
        ...

    def close(self) -> None:
        """關閉引擎別名"""
        self.shutdown()

    @abstractmethod
    def send_key_down(self, key: str) -> bool:
        """按鍵按下"""
        ...

    @abstractmethod
    def send_key_up(self, key: str) -> bool:
        """按鍵釋放"""
        ...

    def send_key_click(self, key: str, hold_ms: int = 0) -> bool:
        """按鍵點擊（按下+釋放）"""
        import time
        ok = self.send_key_down(key)
        if hold_ms > 0:
            time.sleep(hold_ms / 1000.0)
        ok = self.send_key_up(key) and ok
        return ok

    @abstractmethod
    def send_mouse_move(self, abs_x: int, abs_y: int) -> bool:
        """移動滑鼠到絕對座標"""
        ...

    @abstractmethod
    def send_mouse_button_down(self, button: str) -> bool:
        """滑鼠按鍵按下（button: 'left'/'right'/'middle'）"""
        ...

    @abstractmethod
    def send_mouse_button_up(self, button: str) -> bool:
        """滑鼠按鍵釋放"""
        ...

    @abstractmethod
    def send_mouse_scroll(self, direction: str, amount: int) -> bool:
        """滾輪（direction: 'up'/'down'/'left'/'right'）"""
        ...

    @property
    @abstractmethod
    def name(self) -> str:
        """引擎名稱"""
        ...

    @property
    @abstractmethod
    def is_available(self) -> bool:
        """引擎是否可用（驅動是否安裝）"""
        ...
