"""Register bundled OFL faces so the notch is not stuck on Segoe/system defaults."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtGui import QFont, QFontDatabase

_FONTS = Path(__file__).resolve().parent / "assets" / "fonts"
_LOADED = False

# Family names as reported by the TTF name tables (Space Grotesk / IBM Plex).
DISPLAY = "Space Grotesk"
UI = "IBM Plex Sans"
MONO = "IBM Plex Mono"


def load_fonts() -> None:
    global _LOADED
    if _LOADED:
        return
    if _FONTS.is_dir():
        for path in sorted(_FONTS.glob("*.ttf")):
            QFontDatabase.addApplicationFont(str(path))
    _LOADED = True


def font(family: str, size: float = 12, weight: QFont.Weight = QFont.Weight.Normal) -> QFont:
    load_fonts()
    face = QFont(family)
    face.setPixelSize(int(size))
    face.setWeight(weight)
    face.setStyleStrategy(
        QFont.StyleStrategy.PreferAntialias | QFont.StyleStrategy.PreferQuality
    )
    face.setStyleHint(QFont.StyleHint.SansSerif)
    face.setHintingPreference(QFont.HintingPreference.PreferFullHinting)
    return face


def display_font(size: float = 13, weight: QFont.Weight = QFont.Weight.DemiBold) -> QFont:
    return font(DISPLAY, size, weight)


def ui_font(size: float = 12, weight: QFont.Weight = QFont.Weight.Normal) -> QFont:
    return font(UI, size, weight)


def mono_font(size: float = 12, weight: QFont.Weight = QFont.Weight.Medium) -> QFont:
    return font(MONO, size, weight)
