"""Dense graphite notch palette — cool mint accent, system UI typography."""

BLACK = "#0B0D10"
GRAPHITE = "#151820"
GRAPHITE_LIGHT = "#1E222A"
BORDER = "#2A303A"
GREEN = "#6EE7B7"
GREEN_DIM = "#1F3D34"
TEXT = "#E8EDF4"
TEXT_MUTED = "#8B93A3"
DANGER = "#F07178"
ACCENT_SOFT = "#24352F"
RADIUS = 22
# Prefer variable / modern system UI faces; avoid Inter/Roboto/Arial as hero.
FONT = "Segoe UI Variable Text"
FONT_FALLBACK = "Segoe UI, SF Pro Text, Helvetica Neue, sans-serif"

STYLESHEET = f"""
* {{ font-family: '{FONT}', {FONT_FALLBACK}; color: {TEXT}; font-size: 12.5px; }}
QWidget {{ background: transparent; }}
QDialog {{ background: {BLACK}; }}
QWidget#Content, QScrollArea, QScrollArea > QWidget > QWidget {{ background: transparent; }}
QWidget#Card, QFrame#Card {{ background: {GRAPHITE}; border: 1px solid {BORDER};
    border-radius: 14px; }}
QWidget#ToolsStrip {{ background: transparent; }}
QLabel {{ border: none; background: transparent; }}
QLabel#Clock {{ font-size: 12.5px; font-weight: 600; letter-spacing: 0.2px; }}
QLabel#Muted {{ color: {TEXT_MUTED}; font-size: 11.5px; }}
QLabel#Title {{ font-size: 18px; font-weight: 600; }}
QLabel#Section {{ color: {TEXT_MUTED}; font-size: 10.5px; font-weight: 600;
    letter-spacing: 0.6px; text-transform: uppercase; }}
QLabel#Big {{ font-size: 48px; font-weight: 300; letter-spacing: -1.5px; }}
QLabel#Toast {{ color: {GREEN}; font-size: 11.5px; font-weight: 600; }}
QPushButton {{ background: {GRAPHITE}; border: 1px solid {BORDER};
    border-radius: 9px; padding: 6px 11px; }}
QPushButton:hover {{ background: {GRAPHITE_LIGHT}; border-color: #3F4A52; }}
QPushButton:pressed {{ background: {GREEN_DIM}; }}
QPushButton:checked {{ background: {GREEN_DIM}; border-color: {GREEN}; }}
QPushButton:disabled {{ color: #59616D; border-color: #22262D; }}
QPushButton:focus {{ border-color: {GREEN}; }}
QPushButton#Tab, QPushButton#IconButton {{ background: transparent; border: 1px solid transparent;
    border-radius: 11px; padding: 0; }}
QPushButton#Tab:hover, QPushButton#IconButton:hover {{ background: {GRAPHITE_LIGHT}; }}
QPushButton#Tab:checked {{ background: {ACCENT_SOFT}; border-color: #355248; }}
QPushButton#Tab:focus, QPushButton#IconButton:focus {{ border-color: {GREEN}; }}
QPushButton#IconButton:checked {{ background: {GREEN_DIM}; border-color: {GREEN}; }}
QPushButton#Primary {{ background: {GREEN_DIM}; border-color: #3D6B58; color: {GREEN}; }}
QPushButton#Danger {{ color: {DANGER}; background: #2A181C; border-color: #59353E; }}
QLineEdit, QTextEdit, QPlainTextEdit, QTextBrowser, QListWidget {{
    background: {GRAPHITE}; border: 1px solid {BORDER}; border-radius: 10px;
    padding: 7px; selection-background-color: {GREEN_DIM}; }}
QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {{ border-color: #4F8A72; }}
QListWidget::item {{ padding: 8px; border-radius: 6px; }}
QListWidget::item:selected {{ background: {GREEN_DIM}; color: {GREEN}; }}
QSpinBox, QComboBox, QDateEdit, QTimeEdit {{ background: {GRAPHITE};
    border: 1px solid {BORDER}; border-radius: 8px; padding: 5px 8px; min-height: 17px; }}
QComboBox QAbstractItemView {{ background: {GRAPHITE}; border: 1px solid {BORDER};
    selection-background-color: {GREEN_DIM}; padding: 5px; }}
QMenu {{ background: {GRAPHITE}; border: 1px solid {BORDER}; padding: 4px; }}
QMenu::item {{ padding: 7px 18px; border-radius: 5px; }}
QMenu::item:selected {{ background: {GREEN_DIM}; color: {GREEN}; }}
QCheckBox {{ spacing: 8px; }}
QCheckBox::indicator {{ width: 15px; height: 15px; border: 1px solid #56616B;
    border-radius: 4px; background: {GRAPHITE}; }}
QCheckBox::indicator:checked {{ background: {GREEN_DIM}; border: 2px solid {GREEN}; }}
QToolTip {{ background: #1E222A; color: {TEXT}; border: 1px solid #424B57;
    padding: 5px 8px; border-radius: 5px; }}
QScrollArea {{ border: none; }}
QScrollBar:vertical {{ background: transparent; width: 6px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: #3C444F; min-height: 22px; border-radius: 3px; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: transparent; }}
QScrollBar:horizontal {{ height: 6px; background: transparent; }}
QScrollBar::handle:horizontal {{ background: #3C444F; border-radius: 3px; }}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}
QSlider::groove:horizontal {{ height: 3px; background: {BORDER}; border-radius: 2px; }}
QSlider::sub-page:horizontal {{ background: {GREEN}; border-radius: 2px; }}
QSlider::handle:horizontal {{ width: 9px; margin: -3px 0; background: {TEXT};
    border-radius: 4px; }}
"""
