from __future__ import annotations

from dataclasses import asdict, dataclass, fields
from typing import Any


@dataclass
class Settings:
    monitor_index: int = 0
    collapse_delay_ms: int = 600
    animation_ms: int = 180
    compact_width: int = 280
    compact_height: int = 42
    compact_media_width: int = 380
    expanded_width: int = 980
    expanded_height: int = 680
    top_margin: int = 10
    clock_24h: bool = True
    weather_city_json: str = ""  # JSON Place salvo pelo widget de clima
    news_auto_refresh: bool = True
    island_position_json: str = ""
    assistant_position_json: str = ""
    appearance: str = "glass"
    layout_version: int = 3

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Settings:
        s = cls()
        for f in fields(cls):
            if f.name in data:
                try:
                    setattr(s, f.name, type(getattr(s, f.name))(data[f.name]))
                except (TypeError, ValueError):
                    pass
        s.collapse_delay_ms = max(0, min(s.collapse_delay_ms, 10_000))
        s.animation_ms = max(50, min(s.animation_ms, 2_000))
        s.monitor_index = max(0, s.monitor_index)
        if "layout_version" not in data or s.layout_version < 2:
            old_defaults = {
                "compact_width": 180,
                "compact_height": 34,
                "compact_media_width": 320,
                "expanded_width": 720,
                "expanded_height": 380,
            }
            for name, previous in old_defaults.items():
                if getattr(s, name) == previous:
                    setattr(s, name, getattr(cls(), name))
            s.layout_version = 2
        if s.layout_version < 3:
            # Glass Crystal dashboard defaults — only bump sizes still on prior presets.
            glass_defaults = {
                "compact_width": (216, 300),
                "compact_height": (44, 46),
                "compact_media_width": (340, 380),
                "expanded_width": (740, 760),
                "expanded_height": (470, 480),
            }
            for name, previous_values in glass_defaults.items():
                if getattr(s, name) in previous_values:
                    setattr(s, name, getattr(cls(), name))
            s.appearance = "glass"
            s.layout_version = 3
        return s
