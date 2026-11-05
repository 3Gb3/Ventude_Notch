"""Signal Bezel — ink void, phosphor accent, Space Grotesk + IBM Plex."""

# Surfaces
BLACK = "#050607"
GRAPHITE = "#0E1014"
GRAPHITE_LIGHT = "#161A21"
BORDER = "#2C3340"
BORDER_SOFT = "#1C212B"

# Signal (sparse — never flood)
GREEN = "#3DFFB0"
GREEN_DIM = "#0F2E24"
ACCENT_SOFT = "#10261E"
SIGNAL_WARM = "#F0C674"  # weather sun only

# Type
TEXT = "#F4F6F8"
TEXT_MUTED = "#7A8494"
TEXT_FAINT = "#4E5666"
DANGER = "#FF6B7A"

RADIUS = 18
RADIUS_CARD = 8
RADIUS_CONTROL = 6

FONT_DISPLAY = "Space Grotesk"
FONT_UI = "IBM Plex Sans"
FONT_MONO = "IBM Plex Mono"
FONT_FALLBACK = "Segoe UI, SF Pro Text, Helvetica Neue, sans-serif"

STYLESHEET = f"""
* {{
    font-family: '{FONT_UI}', {FONT_FALLBACK};
    color: {TEXT};
    font-size: 12px;
}}
QWidget {{ background: transparent; }}
QDialog {{ background: {BLACK}; }}
QWidget#Content, QScrollArea, QScrollArea > QWidget > QWidget {{ background: transparent; }}
QWidget#Card, QFrame#Card {{
    background: {GRAPHITE};
    border: 1px solid {BORDER_SOFT};
    border-radius: {RADIUS_CARD}px;
}}
QWidget#ToolsStrip {{ background: transparent; }}
QLabel {{ border: none; background: transparent; }}
QLabel#Clock {{
    font-family: '{FONT_MONO}', {FONT_FALLBACK};
    font-size: 12px;
    font-weight: 500;
    letter-spacing: 0.6px;
}}
QLabel#Brand {{
    font-family: '{FONT_DISPLAY}', {FONT_FALLBACK};
    font-size: 13px;
    font-weight: 600;
    letter-spacing: 0.4px;
}}
QLabel#Muted {{ color: {TEXT_MUTED}; font-size: 11px; }}
QLabel#Faint {{ color: {TEXT_FAINT}; font-size: 10px; }}
QLabel#Title {{
    font-family: '{FONT_DISPLAY}', {FONT_FALLBACK};
    font-size: 17px;
    font-weight: 600;
    letter-spacing: -0.2px;
}}
QLabel#Section {{
    font-family: '{FONT_DISPLAY}', {FONT_FALLBACK};
    color: {TEXT_FAINT};
    font-size: 9px;
    font-weight: 600;
    letter-spacing: 1.4px;
}}
QLabel#Big {{
    font-family: '{FONT_DISPLAY}', {FONT_FALLBACK};
    font-size: 44px;
    font-weight: 600;
    letter-spacing: -1.8px;
}}
QLabel#HeroTime {{
    font-family: '{FONT_DISPLAY}', {FONT_FALLBACK};
    font-size: 40px;
    font-weight: 600;
    letter-spacing: -1.6px;
}}
QPushButton {{
    font-family: '{FONT_UI}', {FONT_FALLBACK};
    background: {GRAPHITE_LIGHT};
    border: 1px solid {BORDER};
    border-radius: {RADIUS_CONTROL}px;
    padding: 6px 10px;
}}
QPushButton:hover {{ background: #1C222C; border-color: #3A4454; }}
QPushButton:pressed {{ background: {GREEN_DIM}; }}
QPushButton:checked {{ background: {GREEN_DIM}; border-color: {GREEN}; color: {GREEN}; }}
QPushButton:disabled {{ color: {TEXT_FAINT}; border-color: {BORDER_SOFT}; }}
QPushButton:focus {{ border-color: {GREEN}; }}
QPushButton#Tab, QPushButton#IconButton {{
    background: transparent;
    border: 1px solid transparent;
    border-radius: 8px;
    padding: 0;
}}
QPushButton#Tab:hover, QPushButton#IconButton:hover {{ background: {GRAPHITE_LIGHT}; }}
QPushButton#Tab:checked {{
    background: {ACCENT_SOFT};
    border-color: #1A3D30;
}}
QPushButton#Tab:focus, QPushButton#IconButton:focus {{ border-color: {GREEN}; }}
QPushButton#IconButton:checked {{
    background: {GREEN_DIM};
    border-color: {GREEN};
}}
QPushButton#Primary {{
    background: {GREEN_DIM};
    border-color: #1F4A3A;
    color: {GREEN};
    font-weight: 600;
}}
QPushButton#Danger {{
    color: {DANGER};
    background: #1A0E12;
    border-color: #4A2830;
}}
QLineEdit, QTextEdit, QPlainTextEdit, QTextBrowser, QListWidget {{
    font-family: '{FONT_UI}', {FONT_FALLBACK};
    background: {GRAPHITE};
    border: 1px solid {BORDER};
    border-radius: {RADIUS_CONTROL}px;
    padding: 7px 8px;
    selection-background-color: {GREEN_DIM};
}}
QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {{ border-color: #2A6B52; }}
QListWidget::item {{ padding: 7px; border-radius: 4px; }}
QListWidget::item:selected {{ background: {GREEN_DIM}; color: {GREEN}; }}
QSpinBox, QComboBox, QDateEdit, QTimeEdit {{
    font-family: '{FONT_UI}', {FONT_FALLBACK};
    background: {GRAPHITE};
    border: 1px solid {BORDER};
    border-radius: {RADIUS_CONTROL}px;
    padding: 5px 8px;
    min-height: 16px;
}}
QComboBox QAbstractItemView {{
    background: {GRAPHITE};
    border: 1px solid {BORDER};
    selection-background-color: {GREEN_DIM};
    padding: 4px;
}}
QMenu {{ background: {GRAPHITE}; border: 1px solid {BORDER}; padding: 4px; }}
QMenu::item {{ padding: 7px 16px; border-radius: 4px; }}
QMenu::item:selected {{ background: {GREEN_DIM}; color: {GREEN}; }}
QCheckBox {{ spacing: 8px; }}
QCheckBox::indicator {{
    width: 14px; height: 14px;
    border: 1px solid #56616B;
    border-radius: 3px;
    background: {GRAPHITE};
}}
QCheckBox::indicator:checked {{ background: {GREEN_DIM}; border: 2px solid {GREEN}; }}
QToolTip {{
    font-family: '{FONT_UI}', {FONT_FALLBACK};
    background: {GRAPHITE_LIGHT};
    color: {TEXT};
    border: 1px solid {BORDER};
    padding: 5px 8px;
    border-radius: 4px;
}}
QScrollArea {{ border: none; }}
QScrollBar:vertical {{ background: transparent; width: 5px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: #2E3644; min-height: 20px; border-radius: 2px; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: transparent; }}
QScrollBar:horizontal {{ height: 5px; background: transparent; }}
QScrollBar::handle:horizontal {{ background: #2E3644; border-radius: 2px; }}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}
QSlider::groove:horizontal {{ height: 2px; background: {BORDER}; border-radius: 1px; }}
QSlider::sub-page:horizontal {{ background: {GREEN}; border-radius: 1px; }}
QSlider::handle:horizontal {{
    width: 8px; margin: -3px 0;
    background: {TEXT};
    border-radius: 4px;
}}
"""
