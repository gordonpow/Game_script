"""
Macro 巨集資料模型
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
import uuid

from models.node import MacroNode


class PlaybackMode:
    ONCE   = "once"
    LOOP   = "loop"
    REPEAT = "repeat"


@dataclass
class PlaybackSettings:
    """巨集回放設定"""
    mode: str = PlaybackMode.ONCE
    repeat_count: int = 1
    random_delay: bool = False
    random_delay_min_ms: int = 10
    random_delay_max_ms: int = 50

    def to_dict(self) -> Dict[str, Any]:
        return {
            "mode": self.mode,
            "repeat_count": self.repeat_count,
            "random_delay": self.random_delay,
            "random_delay_min_ms": self.random_delay_min_ms,
            "random_delay_max_ms": self.random_delay_max_ms,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "PlaybackSettings":
        return cls(
            mode=d.get("mode", PlaybackMode.ONCE),
            repeat_count=d.get("repeat_count", 1),
            random_delay=d.get("random_delay", False),
            random_delay_min_ms=d.get("random_delay_min_ms", 10),
            random_delay_max_ms=d.get("random_delay_max_ms", 50),
        )


@dataclass
class Macro:
    """巨集：包含一組有序的節點序列"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = "新巨集"
    description: str = ""
    playback: PlaybackSettings = field(default_factory=PlaybackSettings)
    nodes: List[MacroNode] = field(default_factory=list)
    enabled: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "playback": self.playback.to_dict(),
            "nodes": [n.to_dict() for n in self.nodes],
            "enabled": self.enabled,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Macro":
        return cls(
            id=d.get("id", str(uuid.uuid4())),
            name=d.get("name", "新巨集"),
            description=d.get("description", ""),
            playback=PlaybackSettings.from_dict(d.get("playback", {})),
            nodes=[MacroNode.from_dict(n) for n in d.get("nodes", [])],
            enabled=d.get("enabled", True),
        )

    def get_total_duration_ms(self) -> int:
        """估算巨集總時長（毫秒）"""
        total = 0
        for node in self.nodes:
            from models.node import NodeType
            if node.type == NodeType.WAIT_FIXED:
                total += node.duration_ms
            elif node.type == NodeType.WAIT_RANDOM:
                total += (node.min_ms + node.max_ms) // 2
            elif node.type == NodeType.KEY_CLICK:
                total += node.key_hold_ms
            elif node.type == NodeType.MOUSE_MOVE:
                total += node.move_duration_ms
        return total

    # ── 便利屬性映射至 playback ──────────────────────────
    @property
    def playback_mode(self) -> str:
        return self.playback.mode

    @playback_mode.setter
    def playback_mode(self, val: str):
        self.playback.mode = val

    @property
    def loop_count(self) -> int:
        return self.playback.repeat_count

    @loop_count.setter
    def loop_count(self, val: int):
        self.playback.repeat_count = val

    @property
    def random_delay(self) -> bool:
        return self.playback.random_delay

    @random_delay.setter
    def random_delay(self, val: bool):
        self.playback.random_delay = val

    @property
    def min_delay_ms(self) -> int:
        return self.playback.random_delay_min_ms

    @min_delay_ms.setter
    def min_delay_ms(self, val: int):
        self.playback.random_delay_min_ms = val

    @property
    def max_delay_ms(self) -> int:
        return self.playback.random_delay_max_ms

    @max_delay_ms.setter
    def max_delay_ms(self, val: int):
        self.playback.random_delay_max_ms = val

