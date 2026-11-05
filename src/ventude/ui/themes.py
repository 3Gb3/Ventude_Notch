"""A quiet, consistent palette for both floating islands."""

BLACK = "#101215"
GRAPHITE = "#1A1D23"
GRAPHITE_LIGHT = "#242830"
BORDER = "#2B3039"
GREEN = "#8DE0C1"
GREEN_DIM = "#284A40"
TEXT = "#F0F3F7"
TEXT_MUTED = "#8F98A7"
DANGER = "#F18B94"
RADIUS = 28
FONT = "Segoe UI"

STYLESHEET = f"""
* {{ font-family: '{FONT}'; color: {TEXT}; font-size: 13px; }}
QWidget {{ background: transparent; }}
QDialog {{ background: {BLACK}; }}
QWidget#Content, QScrollArea, QScrollArea > QWidget > QWidget {{ background: transparent; }}
QWidget#Card, QFrame#Card {{ background: {GRAPHITE}; border: 1px solid {BORDER};
    border-radius: 18px; }}
QLabel {{ border: none; background: transparent; }}
QLabel#Clock {{ font-size: 13px; font-weight: 600; }}
QLabel#Muted {{ color: {TEXT_MUTED}; font-size: 12px; }}
QLabel#Title {{ font-size: 20px; font-weight: 600; }}
QLabel#Section {{ color: {TEXT_MUTED}; font-size: 11px; font-weight: 600; }}
QLabel#Big {{ font-size: 52px; font-weight: 300; }}
QPushButton {{ background: {GRAPHITE}; border: 1px solid {BORDER};
    border-radius: 10px; padding: 7px 12px; }}
QPushButton:hover {{ background: {GRAPHITE_LIGHT}; border-color: #52605F; }}
QPushButton:pressed {{ background: {GREEN_DIM}; }}
QPushButton:checked {{ background: {GREEN_DIM}; border-color: {GREEN}; }}
QPushButton:disabled {{ color: #59616D; border-color: #22262D; }}
QPushButton:focus {{ border-color: {GREEN}; }}
QPushButton#Tab, QPushButton#IconButton {{ background: transparent; border: 1px solid transparent;
    border-radius: 13px; padding: 0; }}
QPushButton#Tab:hover, QPushButton#IconButton:hover {{ background: {GRAPHITE_LIGHT}; }}
QPushButton#Tab:checked {{ background: {GREEN_DIM}; border-color: #3E6255; }}
QPushButton#Tab:focus, QPushButton#IconButton:focus {{ border-color: {GREEN}; }}
QPushButton#Primary {{ background: {GREEN_DIM}; border-color: #426F5E; color: {GREEN}; }}
QPushButton#Danger {{ color: {DANGER}; background: #312127; border-color: #59353E; }}
QLineEdit, QTextEdit, QPlainTextEdit, QTextBrowser, QListWidget {{
    background: {GRAPHITE}; border: 1px solid {BORDER}; border-radius: 12px;
    padding: 8px; selection-background-color: {GREEN_DIM}; }}
QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {{ border-color: #5B9580; }}
QListWidget::item {{ padding: 9px; border-radius: 7px; }}
QListWidget::item:selected {{ background: {GREEN_DIM}; color: {GREEN}; }}
QSpinBox, QComboBox, QDateEdit, QTimeEdit {{ background: {GRAPHITE};
    border: 1px solid {BORDER}; border-radius: 9px; padding: 6px 9px; min-height: 18px; }}
QComboBox QAbstractItemView {{ background: {GRAPHITE}; border: 1px solid {BORDER};
    selection-background-color: {GREEN_DIM}; padding: 6px; }}
QMenu {{ background: {GRAPHITE}; border: 1px solid {BORDER}; padding: 5px; }}
QMenu::item {{ padding: 8px 20px; border-radius: 6px; }}
QMenu::item:selected {{ background: {GREEN_DIM}; color: {GREEN}; }}
QCheckBox {{ spacing: 9px; }}
QCheckBox::indicator {{ width: 16px; height: 16px; border: 1px solid #56616B;
    border-radius: 5px; background: {GRAPHITE}; }}
QCheckBox::indicator:checked {{ background: {GREEN_DIM}; border: 2px solid {GREEN}; }}
QToolTip {{ background: #242830; color: {TEXT}; border: 1px solid #424B57;
    padding: 6px 9px; border-radius: 6px; }}
QScrollArea {{ border: none; }}
QScrollBar:vertical {{ background: transparent; width: 7px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: #3C444F; min-height: 24px; border-radius: 3px; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: transparent; }}
QScrollBar:horizontal {{ height: 7px; background: transparent; }}
QScrollBar::handle:horizontal {{ background: #3C444F; border-radius: 3px; }}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}
QSlider::groove:horizontal {{ height: 4px; background: {BORDER}; border-radius: 2px; }}
QSlider::sub-page:horizontal {{ background: {GREEN}; border-radius: 2px; }}
QSlider::handle:horizontal {{ width: 10px; margin: -3px 0; background: {TEXT};
    border-radius: 5px; }}
"""
