from __future__ import annotations

import json

from PySide6.QtCore import QEasingCurve, QPoint, QPropertyAnimation, QRect, QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QCursor, QMouseEvent, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QLayout,
    QLineEdit,
    QPlainTextEdit,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ventude.core.config import Settings
from ventude.core.events import EventBus
from ventude.services.monitors import screen_for, screens
from ventude.storage.database import Database
from ventude.ui import themes
from ventude.ui.icons import icon, icon_button


def anchored_rect(area: QRect, width: int, height: int, anchor: QPoint) -> QRect:
    """Keep center/top anchor visible, including on negative-coordinate monitors."""
    width, height = min(width, area.width() - 16), min(height, area.height() - 16)
    x = max(area.left() + 8, min(anchor.x() - width // 2, area.right() - width - 7))
    y = max(area.top() + 8, min(anchor.y(), area.bottom() - height - 7))
    return QRect(x, y, width, height)


class DragHeader(QWidget):
    """A grab surface; child controls keep their normal click behavior."""

    def __init__(self, island: FloatingIsland) -> None:
        super().__init__(island)
        self.island = island
        self.press_at: QPoint | None = None
        self.moved = False
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self.setToolTip("Segure e arraste para mover para qualquer monitor")
        self.setFixedHeight(28)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() != Qt.MouseButton.LeftButton:
            return
        self.island.anim.stop()
        self.island.hover_timer.stop()
        self.island.collapse_timer.stop()
        self.island._dragging = True
        self.press_at = event.globalPosition().toPoint()
        self.origin = self.island.pos()
        self.moved = False
        self.setCursor(Qt.CursorShape.ClosedHandCursor)
        event.accept()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self.press_at is None:
            return
        delta = event.globalPosition().toPoint() - self.press_at
        if delta.manhattanLength() >= QApplication.startDragDistance():
            self.moved = True
        if self.moved:
            self.island.move(self.origin + delta)
        event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if self.press_at is None or event.button() != Qt.MouseButton.LeftButton:
            return
        self.press_at = None
        self.island._dragging = False
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        if self.moved:
            self.island.save_position()
            self.island.reposition()
        else:
            self.island.animate_to(True)
        if not self.island.geometry().contains(QCursor.pos()):
            self.island.collapse_timer.start(self.island.settings.collapse_delay_ms)
        event.accept()


class FloatingIsland(QWidget):
    def __init__(
        self,
        settings: Settings,
        db: Database,
        bus: EventBus,
        *,
        position_key: str,
        title: str,
        symbol: str,
    ) -> None:
        super().__init__(
            None,
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool,
        )
        self.settings, self.db, self.bus = settings, db, bus
        self.position_key = position_key
        self.expanded = False
        self._dragging = False
        self._menus_open = 0
        self._bg_cache: QPixmap | None = None
        self._bg_cache_key: tuple[int, int, int] | None = None
        self._content_revealed = False
        self.setWindowTitle(title)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        # Geometry animation only; avoid per-frame layout/content churn.
        self.anim = QPropertyAnimation(self, b"geometry", self)
        self.anim.setEasingCurve(QEasingCurve.Type.OutQuint)
        self.anim.valueChanged.connect(self._on_anim_frame)
        self.anim.finished.connect(self._on_anim_finished)
        self.hover_timer = QTimer(
            self, singleShot=True, interval=120, timeout=lambda: self.animate_to(True)
        )
        self.collapse_timer = QTimer(self, singleShot=True, timeout=self._try_collapse)
        bus.menu_opened.connect(self._on_menu_opened)
        bus.menu_closed.connect(self._on_menu_closed)

        root = QVBoxLayout(self)
        root.setSizeConstraint(QLayout.SizeConstraint.SetNoConstraint)
        root.setContentsMargins(14, 7, 14, 12)
        root.setSpacing(8)
        self.header = DragHeader(self)
        top = QHBoxLayout(self.header)
        top.setContentsMargins(0, 0, 0, 0)
        top.setSpacing(8)
        self.mark = QLabel()
        self.mark.setPixmap(icon(symbol, themes.GREEN, 18).pixmap(18, 18))
        self.mark.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.clock = QLabel(title)
        self.clock.setObjectName("Clock")
        self.clock.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.clock.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        top.addWidget(self.mark)
        top.addWidget(self.clock, 1)
        self.tools_host = QWidget()
        self.tools_host.setObjectName("ToolsStrip")
        self.tools_layout = QHBoxLayout(self.tools_host)
        self.tools_layout.setContentsMargins(0, 0, 0, 0)
        self.tools_layout.setSpacing(2)
        top.addWidget(self.tools_host, 0, Qt.AlignmentFlag.AlignVCenter)
        self.grip = QLabel()
        self.grip.setPixmap(icon("grip", themes.TEXT_MUTED, 16).pixmap(16, 16))
        self.grip.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        top.addWidget(self.grip)
        self.collapse_button = icon_button("chevron-down", "Recolher ilha", 26)
        self.collapse_button.clicked.connect(lambda: self.animate_to(False))
        top.addWidget(self.collapse_button)
        root.addWidget(self.header)
        self.content = QWidget()
        self.content.setObjectName("Content")
        self.content.hide()
        root.addWidget(self.content, 1)

    def _sizes(self, expanded: bool) -> tuple[int, int]:
        raise NotImplementedError

    def _default_anchor(self, area: QRect) -> QPoint:
        return QPoint(area.center().x(), area.y() + self.settings.top_margin)

    def _position(self) -> tuple[QRect, QPoint]:
        fallback = screen_for(self.settings.monitor_index).availableGeometry()
        try:
            saved = json.loads(getattr(self.settings, self.position_key))
            anchor = QPoint(int(saved["x"]), int(saved["y"]))
            for screen in screens():
                if screen.geometry().contains(anchor):
                    return screen.availableGeometry(), anchor
        except (ValueError, TypeError, KeyError, OverflowError):
            pass
        return fallback, self._default_anchor(fallback)

    def _target_rect(self, expanded: bool) -> QRect:
        area, anchor = self._position()
        return anchored_rect(area, *self._sizes(expanded), anchor)

    def _apply_chrome(self, *, show_content: bool) -> None:
        self.content.setVisible(show_content)
        self.collapse_button.setVisible(self.expanded)
        self.grip.setVisible(True)
        self._content_revealed = show_content

    def _on_anim_frame(self, value: QRect) -> None:
        # Reveal content once during expand; never toggle every frame.
        if self.expanded and not self._content_revealed and value.height() > 96:
            self._apply_chrome(show_content=True)

    def _on_anim_finished(self) -> None:
        self._apply_chrome(show_content=self.expanded)
        self._invalidate_bg_cache()

    def animate_to(self, expanded: bool) -> None:
        if self._dragging:
            return
        self.hover_timer.stop()
        target = self._target_rect(expanded)
        if expanded == self.expanded and self.geometry() == target:
            return
        self.expanded = expanded
        self.anim.stop()
        self.anim.setDuration(self.settings.animation_ms)
        self.anim.setStartValue(self.geometry())
        self.anim.setEndValue(target)
        if not expanded:
            # Hide early so collapse does not layout a shrinking dashboard.
            self._apply_chrome(show_content=False)
        else:
            self.collapse_button.setVisible(True)
            self._content_revealed = False
        self._invalidate_bg_cache()
        self.anim.start()

    def reposition(self) -> None:
        self.anim.stop()
        self.setGeometry(self._target_rect(self.expanded))
        self._apply_chrome(show_content=self.expanded)
        self._invalidate_bg_cache()

    def save_position(self) -> None:
        anchor = QPoint(self.x() + self.width() // 2, self.y())
        screen = QApplication.screenAt(anchor) or screen_for(self.settings.monitor_index)
        rect = anchored_rect(screen.availableGeometry(), self.width(), self.height(), anchor)
        anchor = QPoint(rect.x() + rect.width() // 2, rect.y())
        setattr(self.settings, self.position_key, json.dumps({"x": anchor.x(), "y": anchor.y()}))
        if self.position_key == "island_position_json":
            self.settings.monitor_index = screens().index(screen)
            self.bus.monitor_changed.emit(self.settings.monitor_index)
        self.db.save_settings(self.settings)

    def _invalidate_bg_cache(self) -> None:
        self._bg_cache = None
        self._bg_cache_key = None

    def _ensure_bg_cache(self) -> QPixmap:
        w, h = self.width(), self.height()
        radius = int(min(themes.RADIUS, h / 2))
        key = (w, h, radius)
        if self._bg_cache is not None and self._bg_cache_key == key:
            return self._bg_cache
        dpr = max(1.0, float(self.devicePixelRatioF()))
        pm = QPixmap(int(w * dpr), int(h * dpr))
        pm.setDevicePixelRatio(dpr)
        pm.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pm)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rect = QRectF(0.5, 0.5, w - 1.0, h - 1.0)
        path = QPainterPath()
        path.addRoundedRect(rect, radius, radius)
        painter.fillPath(path, QColor(themes.BLACK))
        painter.setPen(QPen(QColor(themes.BORDER), 1))
        painter.drawPath(path)
        painter.end()
        self._bg_cache = pm
        self._bg_cache_key = key
        return pm

    def paintEvent(self, _event: object) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        painter.drawPixmap(0, 0, self._ensure_bg_cache())

    def resizeEvent(self, event: object) -> None:
        super().resizeEvent(event)
        # Geometry animation changes size every frame — rebuild cache only when
        # dimensions leave the previous bucket (handled lazily in paint).
        if self._bg_cache_key and (
            self._bg_cache_key[0] != self.width() or self._bg_cache_key[1] != self.height()
        ):
            self._invalidate_bg_cache()

    def enterEvent(self, _event: object) -> None:
        self.collapse_timer.stop()
        if not self.expanded and not self._dragging:
            self.hover_timer.start()

    def leaveEvent(self, _event: object) -> None:
        self.hover_timer.stop()
        if not self._dragging:
            self.collapse_timer.start(self.settings.collapse_delay_ms)

    def _typing(self) -> bool:
        widget = QApplication.focusWidget()
        if widget is None or not self.isAncestorOf(widget):
            return False
        if isinstance(widget, QLineEdit):
            return bool(widget.text())
        return isinstance(widget, (QTextEdit, QPlainTextEdit)) and not widget.isReadOnly()

    def _keep_open(self) -> bool:
        return False

    def _menu_is_open(self) -> bool:
        return (
            self._menus_open > 0
            or QApplication.activePopupWidget() is not None
            or QApplication.activeModalWidget() is not None
        )

    def _try_collapse(self) -> None:
        if (
            self._dragging
            or self._menu_is_open()
            or self.geometry().contains(QCursor.pos())
            or self._typing()
            or self._keep_open()
        ):
            self.collapse_timer.start(max(200, self.settings.collapse_delay_ms))
            return
        self.animate_to(False)

    def _on_menu_opened(self) -> None:
        self._menus_open += 1
        self.collapse_timer.stop()

    def _on_menu_closed(self) -> None:
        self._menus_open = max(0, self._menus_open - 1)
        self.collapse_timer.start(self.settings.collapse_delay_ms)

    def reveal(self) -> None:
        self.show()
        self.raise_()
        self.animate_to(True)

    def hide_island(self) -> None:
        self.animate_to(False)
        self.hide()

    def closeEvent(self, event: object) -> None:
        self.hide()
        event.ignore()
