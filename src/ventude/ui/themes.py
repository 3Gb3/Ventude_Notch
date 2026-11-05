"""Glass Crystal — frosted light neutrals, Spotify-mint accent, soft geometry."""

# Frosted surfaces (RGB used by painters; QSS uses rgba where needed)
GLASS = "#F4F7FB"
GLASS_STRONG = "#FFFFFF"
GLASS_SOFT = "#EEF2F7"
GLASS_EDGE = "#D7DEE8"
GLASS_EDGE_SOFT = "#E8EEF5"

# Keep legacy aliases so older widgets still resolve.
BLACK = GLASS_STRONG
GRAPHITE = GLASS
GRAPHITE_LIGHT = GLASS_SOFT
BORDER = GLASS_EDGE
BORDER_SOFT = GLASS_EDGE_SOFT

# Spotify-like mint for active / signal states
GREEN = "#1DB954"
GREEN_DIM = "#D8F5E3"
GREEN_DEEP = "#149643"
ACCENT_SOFT = "#E7F8EE"
SIGNAL_WARM = "#F5B942"

TEXT = "#111827"
TEXT_MUTED = "#6B7280"
TEXT_FAINT = "#9CA3AF"
DANGER = "#E11D48"

# Painter alpha for the island shell (true OS backdrop blur is limited in Qt).
SHELL_FILL = (255, 255, 255, 210)
SHELL_BORDER = (255, 255, 255, 235)
SHELL_INNER = (255, 255, 255, 90)
CARD_FILL = (255, 255, 255, 175)

RADIUS = 28
RADIUS_CARD = 22
RADIUS_CONTROL = 16
RADIUS_PILL = 999

FONT_DISPLAY = "Space Grotesk"
FONT_UI = "IBM Plex Sans"
FONT_MONO = "IBM Plex Mono"
FONT_FALLBACK = "Segoe UI Variable Text, Segoe UI, SF Pro Text, sans-serif"

STYLESHEET = f"""
* {{
    font-family: '{FONT_UI}', {FONT_FALLBACK};
    color: {TEXT};
    font-size: 12px;
}}
QWidget {{ background: transparent; }}
QDialog {{ background: {GLASS_STRONG}; }}
QWidget#Content, QScrollArea, QScrollArea > QWidget > QWidget {{ background: transparent; }}
QWidget#Card, QFrame#Card {{
    background: rgba(255, 255, 255, 175);
    border: 1px solid {GLASS_EDGE_SOFT};
    border-radius: {RADIUS_CARD}px;
}}
QWidget#GlassPill {{
    background: rgba(255, 255, 255, 190);
    border: 1px solid {GLASS_EDGE};
    border-radius: 18px;
}}
QWidget#ToolsStrip {{ background: transparent; }}
QLabel {{ border: none; background: transparent; }}
QLabel#Clock {{
    font-family: '{FONT_MONO}', {FONT_FALLBACK};
    font-size: 12px;
    font-weight: 500;
    letter-spacing: 0.4px;
    color: {TEXT};
}}
QLabel#Brand {{
    font-family: '{FONT_DISPLAY}', {FONT_FALLBACK};
    font-size: 13px;
    font-weight: 600;
    letter-spacing: 0.2px;
    color: {TEXT};
}}
QLabel#Muted {{ color: {TEXT_MUTED}; font-size: 11px; }}
QLabel#Faint {{ color: {TEXT_FAINT}; font-size: 10px; }}
QLabel#Title {{
    font-family: '{FONT_DISPLAY}', {FONT_FALLBACK};
    font-size: 16px;
    font-weight: 600;
    letter-spacing: -0.2px;
}}
QLabel#Section {{
    font-family: '{FONT_DISPLAY}', {FONT_FALLBACK};
    color: {TEXT_MUTED};
    font-size: 10px;
    font-weight: 600;
    letter-spacing: 0.8px;
}}
QLabel#Big, QLabel#HeroTime {{
    font-family: '{FONT_DISPLAY}', {FONT_FALLBACK};
    font-size: 28px;
    font-weight: 700;
    letter-spacing: -0.8px;
    color: {TEXT};
}}
QLabel#HeroDate {{
    font-family: '{FONT_DISPLAY}', {FONT_FALLBACK};
    font-size: 22px;
    font-weight: 700;
    letter-spacing: -0.4px;
}}
QPushButton {{
    font-family: '{FONT_UI}', {FONT_FALLBACK};
    background: rgba(255, 255, 255, 200);
    border: 1px solid {GLASS_EDGE};
    border-radius: {RADIUS_CONTROL}px;
    padding: 6px 12px;
    color: {TEXT};
}}
QPushButton:hover {{ background: rgba(255, 255, 255, 235); border-color: #C5CEDA; }}
QPushButton:pressed {{ background: {GREEN_DIM}; }}
QPushButton:checked {{
    background: {GREEN};
    border-color: {GREEN};
    color: white;
}}
QPushButton:disabled {{ color: {TEXT_FAINT}; border-color: {GLASS_EDGE_SOFT}; }}
QPushButton:focus {{ border-color: {GREEN}; }}
QPushButton#Tab, QPushButton#IconButton {{
    background: transparent;
    border: 1px solid transparent;
    border-radius: 14px;
    padding: 0;
}}
QPushButton#Tab:hover, QPushButton#IconButton:hover {{
    background: rgba(255, 255, 255, 160);
}}
QPushButton#Tab:checked {{
    background: {GREEN};
    border-color: {GREEN};
}}
QPushButton#IconButton:checked {{
    background: {GREEN_DIM};
    border-color: {GREEN};
}}
QPushButton#Primary {{
    background: {GREEN};
    border-color: {GREEN};
    color: white;
    font-weight: 600;
    border-radius: 18px;
}}
QPushButton#Primary:hover {{ background: {GREEN_DEEP}; border-color: {GREEN_DEEP}; }}
QPushButton#Danger {{
    color: {DANGER};
    background: #FFF1F2;
    border-color: #FECDD3;
}}
QPushButton#AskAI {{
    background: rgba(255, 255, 255, 200);
    border: 1px solid {GLASS_EDGE};
    border-radius: 22px;
    text-align: left;
    padding: 10px 14px;
    color: {TEXT_MUTED};
    font-size: 13px;
}}
QPushButton#AskAI:hover {{ background: rgba(255, 255, 255, 240); color: {TEXT}; }}
QLineEdit, QTextEdit, QPlainTextEdit, QTextBrowser, QListWidget {{
    font-family: '{FONT_UI}', {FONT_FALLBACK};
    background: rgba(255, 255, 255, 200);
    border: 1px solid {GLASS_EDGE};
    border-radius: {RADIUS_CONTROL}px;
    padding: 7px 10px;
    selection-background-color: {GREEN_DIM};
    color: {TEXT};
}}
QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {{ border-color: {GREEN}; }}
QListWidget::item {{ padding: 7px; border-radius: 10px; }}
QListWidget::item:selected {{ background: {GREEN_DIM}; color: {TEXT}; }}
QSpinBox, QComboBox, QDateEdit, QTimeEdit {{
    font-family: '{FONT_UI}', {FONT_FALLBACK};
    background: rgba(255, 255, 255, 200);
    border: 1px solid {GLASS_EDGE};
    border-radius: 12px;
    padding: 5px 8px;
    min-height: 16px;
}}
QComboBox QAbstractItemView {{
    background: {GLASS_STRONG};
    border: 1px solid {GLASS_EDGE};
    selection-background-color: {GREEN_DIM};
    padding: 4px;
}}
QMenu {{ background: {GLASS_STRONG}; border: 1px solid {GLASS_EDGE}; padding: 4px; }}
QMenu::item {{ padding: 7px 16px; border-radius: 8px; }}
QMenu::item:selected {{ background: {GREEN_DIM}; color: {TEXT}; }}
QCheckBox {{ spacing: 8px; color: {TEXT}; }}
QCheckBox::indicator {{
    width: 14px; height: 14px;
    border: 1px solid {GLASS_EDGE};
    border-radius: 4px;
    background: white;
}}
QCheckBox::indicator:checked {{ background: {GREEN}; border: 2px solid {GREEN}; }}
QToolTip {{
    font-family: '{FONT_UI}', {FONT_FALLBACK};
    background: {GLASS_STRONG};
    color: {TEXT};
    border: 1px solid {GLASS_EDGE};
    padding: 5px 8px;
    border-radius: 8px;
}}
QScrollArea {{ border: none; }}
QScrollBar:vertical {{ background: transparent; width: 5px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: #C5CEDA; min-height: 20px; border-radius: 2px; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: transparent; }}
QScrollBar:horizontal {{ height: 5px; background: transparent; }}
QScrollBar::handle:horizontal {{ background: #C5CEDA; border-radius: 2px; }}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}
QSlider::groove:horizontal {{ height: 4px; background: {GLASS_EDGE}; border-radius: 2px; }}
QSlider::sub-page:horizontal {{ background: {GREEN}; border-radius: 2px; }}
QSlider::handle:horizontal {{
    width: 12px; margin: -4px 0;
    background: {GREEN};
    border-radius: 6px;
}}
"""
