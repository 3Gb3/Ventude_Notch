"""Screen capture helpers: pixel color sampling and region screenshots."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QPoint, QRect, QRectF, Qt
from PySide6.QtGui import (
    QColor,
    QCursor,
    QGuiApplication,
    QImage,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
)
from PySide6.QtWidgets import QApplication, QLabel, QWidget


@dataclass(frozen=True)
class SampledColor:
    hex: str
    rgb: tuple[int, int, int]

    @property
    def clipboard_text(self) -> str:
        r, g, b = self.rgb
        return f"{self.hex}  rgb({r}, {g}, {b})"


def cursor_pos() -> QPoint:
    return QCursor.pos()


def grab_screen(rect: QRect | None = None) -> QPixmap:
    screen = QGuiApplication.screenAt(cursor_pos()) or QGuiApplication.primaryScreen()
    if screen is None:
        return QPixmap()
    geo = screen.geometry()
    grab = screen.grabWindow(0)
    if rect is None:
        return grab
    local = QRect(rect.x() - geo.x(), rect.y() - geo.y(), rect.width(), rect.height())
    return grab.copy(local.intersected(QRect(0, 0, grab.width(), grab.height())))


def sample_color_at(global_pos: QPoint) -> SampledColor | None:
    screen = QGuiApplication.screenAt(global_pos) or QGuiApplication.primaryScreen()
    if screen is None:
        return None
    geo = screen.geometry()
    dpr = screen.devicePixelRatio()
    local_x = int((global_pos.x() - geo.x()) * dpr)
    local_y = int((global_pos.y() - geo.y()) * dpr)
    grab = screen.grabWindow(0, local_x, local_y, max(1, int(dpr)), max(1, int(dpr)))
    image = grab.toImage()
    if image.isNull():
        return None
    color = QColor(image.pixel(0, 0))
    return SampledColor(
        hex=color.name().upper(),
        rgb=(color.red(), color.green(), color.blue()),
    )


def copy_text(text: str) -> None:
    clipboard = QApplication.clipboard()
    if clipboard is not None:
        clipboard.setText(text)


def copy_image(pixmap: QPixmap) -> None:
    clipboard = QApplication.clipboard()
    if clipboard is not None:
        clipboard.setPixmap(pixmap)


def _virtual_desktop() -> QRect:
    virtual = QRect()
    for screen in QGuiApplication.screens():
        virtual = virtual.united(screen.geometry())
    return virtual


class RegionOverlay(QWidget):
    """Fullscreen dim overlay for selecting a screen rectangle."""

    def __init__(self, on_done) -> None:
        super().__init__(
            None,
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool,
        )
        self._on_done = on_done
        self._origin: QPoint | None = None
        self._current: QPoint | None = None
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.setMouseTracking(True)
        self.setGeometry(_virtual_desktop())
        hint = QLabel("Arraste para selecionar · Esc cancela", self)
        hint.setStyleSheet(
            "color:#E8EDF4; background:rgba(11,13,16,180); padding:8px 12px; border-radius:8px;"
        )
        hint.adjustSize()
        hint.move(24, 24)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        self.activateWindow()
        self.setFocus(Qt.FocusReason.ActiveWindowFocusReason)
        self.grabKeyboard()

    def keyPressEvent(self, event) -> None:  # noqa: N802
        if event.key() == Qt.Key.Key_Escape:
            self._finish(None)
        else:
            super().keyPressEvent(event)

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self._origin = event.globalPosition().toPoint()
            self._current = self._origin
            self.update()

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        if self._origin is not None:
            self._current = event.globalPosition().toPoint()
            self.update()

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        if event.button() != Qt.MouseButton.LeftButton or self._origin is None:
            return
        end = event.globalPosition().toPoint()
        rect = QRect(self._origin, end).normalized()
        self._finish(rect if rect.width() >= 4 and rect.height() >= 4 else None)

    def paintEvent(self, _event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        dim = QPainterPath()
        dim.addRect(QRectF(self.rect()))
        if self._origin is not None and self._current is not None:
            hole = QRect(
                self.mapFromGlobal(self._origin), self.mapFromGlobal(self._current)
            ).normalized()
            cut = QPainterPath()
            cut.addRect(QRectF(hole))
            dim = dim.subtracted(cut)
            painter.fillPath(dim, QColor(0, 0, 0, 120))
            painter.setPen(QPen(QColor("#6EE7B7"), 1.5))
            painter.drawRect(hole.adjusted(0, 0, -1, -1))
        else:
            painter.fillPath(dim, QColor(0, 0, 0, 120))

    def _finish(self, rect: QRect | None) -> None:
        self.releaseKeyboard()
        callback = self._on_done
        self.close()
        self.deleteLater()
        callback(rect)


class ColorPickOverlay(QWidget):
    """Click anywhere to sample a pixel color."""

    def __init__(self, on_done) -> None:
        super().__init__(
            None,
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool,
        )
        self._on_done = on_done
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.setMouseTracking(True)
        self.setGeometry(_virtual_desktop())
        self._swatch = QLabel(self)
        self._swatch.setFixedSize(56, 56)
        self._swatch.setStyleSheet(
            "border:2px solid #E8EDF4; border-radius:8px; background:#000;"
        )
        self._label = QLabel("#------", self)
        self._label.setStyleSheet(
            "color:#E8EDF4; background:rgba(11,13,16,200); padding:6px 10px;"
            " border-radius:8px; font-weight:600;"
        )
        hint = QLabel("Clique para copiar a cor · Esc cancela", self)
        hint.setStyleSheet(
            "color:#E8EDF4; background:rgba(11,13,16,180); padding:8px 12px; border-radius:8px;"
        )
        hint.adjustSize()
        hint.move(24, 24)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        self.activateWindow()
        self.setFocus(Qt.FocusReason.ActiveWindowFocusReason)
        self.grabKeyboard()

    def keyPressEvent(self, event) -> None:  # noqa: N802
        if event.key() == Qt.Key.Key_Escape:
            self._finish(None)
        else:
            super().keyPressEvent(event)

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        pos = event.globalPosition().toPoint()
        sample = sample_color_at(pos)
        local = self.mapFromGlobal(pos)
        self._swatch.move(local.x() + 18, local.y() + 18)
        self._label.move(local.x() + 18, local.y() + 82)
        if sample:
            self._swatch.setStyleSheet(
                f"border:2px solid #E8EDF4; border-radius:8px; background:{sample.hex};"
            )
            self._label.setText(sample.hex)
            self._label.adjustSize()

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self._finish(sample_color_at(event.globalPosition().toPoint()))

    def paintEvent(self, _event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(0, 0, 0, 40))

    def _finish(self, color: SampledColor | None) -> None:
        self.releaseKeyboard()
        callback = self._on_done
        self.close()
        self.deleteLater()
        callback(color)


def pixmap_to_image(pixmap: QPixmap) -> QImage:
    return pixmap.toImage().convertToFormat(QImage.Format.Format_RGBA8888)
