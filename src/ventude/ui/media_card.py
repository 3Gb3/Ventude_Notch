from __future__ import annotations

from PySide6.QtCore import QRectF, Qt, QTimer
from PySide6.QtGui import QPainter, QPainterPath, QPixmap
from PySide6.QtWidgets import QHBoxLayout, QLabel, QSizePolicy, QSlider, QVBoxLayout, QWidget

from ventude.services.media import STATUS_LABELS, MediaService, MediaState, format_time
from ventude.ui import themes
from ventude.ui.icons import icon, icon_button

ART = 56


class MediaCard(QWidget):
    """Real Windows media, presented as a quiet, compact transport card."""

    def __init__(self, service: MediaService) -> None:
        super().__init__()
        self.service = service
        self.state: MediaState | None = None
        self._dragging = False
        self.setObjectName("Card")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground)
        self.setMinimumHeight(92)
        row = QHBoxLayout(self)
        row.setContentsMargins(12, 10, 12, 10)
        row.setSpacing(12)
        self.art = QLabel()
        self.art.setFixedSize(ART, ART)
        self.art.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.art.setStyleSheet(
            f"background:{themes.GRAPHITE_LIGHT}; border-radius:{themes.RADIUS_CARD}px;"
        )
        row.addWidget(self.art)

        self.media_box = QWidget()
        col = QVBoxLayout(self.media_box)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(2)
        self.title = QLabel()
        self.title.setStyleSheet(
            f"font-family:'{themes.FONT_DISPLAY}'; font-size:13px; font-weight:600;"
        )
        self.title.setTextFormat(Qt.TextFormat.PlainText)
        self.artist = QLabel()
        self.artist.setObjectName("Muted")
        self.artist.setTextFormat(Qt.TextFormat.PlainText)
        self.status = QLabel(self)
        self.status.hide()
        for label in (self.title, self.artist):
            label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
            col.addWidget(label)
        bar = QHBoxLayout()
        bar.setSpacing(8)
        self.pos = QLabel("0:00")
        self.pos.setObjectName("Muted")
        self.pos.setStyleSheet("font-size:10px;")
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setAccessibleName("Posição da música")
        self.slider.setStyleSheet(
            f"QSlider::groove:horizontal {{ height:3px; background:{themes.BORDER};"
            " border-radius:1px; }"
            f"QSlider::sub-page:horizontal {{ background:{themes.GREEN}; border-radius:1px; }}"
            f"QSlider::handle:horizontal {{ width:8px; margin:-3px 0; border-radius:4px;"
            f" background:{themes.TEXT}; }}"
        )
        self.slider.sliderPressed.connect(self._press)
        self.slider.sliderReleased.connect(self._release)
        self.dur = QLabel("0:00")
        self.dur.setObjectName("Muted")
        self.dur.setStyleSheet("font-size:10px;")
        bar.addWidget(self.pos)
        bar.addWidget(self.slider, 1)
        bar.addWidget(self.dur)
        col.addLayout(bar)
        row.addWidget(self.media_box, 1)

        self.empty = QLabel("Nenhuma mídia tocando\nAbra uma música ou um vídeo para começar.")
        self.empty.setObjectName("Muted")
        self.empty.setWordWrap(True)
        row.addWidget(self.empty, 1)
        self.controls = QWidget()
        buttons = QHBoxLayout(self.controls)
        buttons.setContentsMargins(0, 0, 0, 0)
        buttons.setSpacing(4)
        self.prev_btn = icon_button("skip-back", "Faixa anterior", 32)
        self.play_btn = icon_button("play", "Reproduzir ou pausar", 40)
        self.play_btn.setObjectName("Primary")
        self.next_btn = icon_button("skip-forward", "Próxima faixa", 32)
        self.prev_btn.clicked.connect(service.previous)
        self.play_btn.clicked.connect(service.play_pause)
        self.next_btn.clicked.connect(service.next)
        for button in (self.prev_btn, self.play_btn, self.next_btn):
            buttons.addWidget(button)
        row.addWidget(self.controls)

        self.tick = QTimer(self, interval=500, timeout=self._update_progress)
        service.state_changed.connect(self.set_state)
        service.thumbnail_changed.connect(self.set_thumbnail)
        self.set_state(service.state)
        self.set_thumbnail(b"")

    def set_state(self, state: MediaState | None) -> None:
        self.state = state
        has = state is not None
        self.media_box.setVisible(has)
        self.controls.setVisible(has)
        self.empty.setVisible(not has)
        if not state:
            self.tick.stop()
            self.set_thumbnail(b"")
            return
        self._update_labels()
        self.status.setText(STATUS_LABELS.get(state.status, state.status))
        self.setToolTip(self.status.text())
        self.play_btn.setIcon(icon("pause" if state.is_playing else "play", themes.TEXT))
        self.play_btn.setToolTip("Pausar" if state.is_playing else "Reproduzir")
        self.play_btn.setAccessibleName(self.play_btn.toolTip())
        self.play_btn.setEnabled(state.can_play_pause)
        self.prev_btn.setEnabled(state.can_previous)
        self.next_btn.setEnabled(state.can_next)
        self.slider.setEnabled(state.can_seek)
        self.slider.setRange(0, int(state.duration_s * 1000))
        self.dur.setText(format_time(state.duration_s) if state.duration_s > 0 else "—")
        self._update_progress()
        if state.is_playing and state.duration_s > 0:
            self.tick.start()
        else:
            self.tick.stop()

    def _update_labels(self) -> None:
        if not self.state:
            return
        for label, value in (
            (self.title, self.state.title),
            (self.artist, " · ".join(x for x in (self.state.artist, self.state.album) if x)),
        ):
            label.setToolTip(value)
            label.setText(
                label.fontMetrics().elidedText(
                    value, Qt.TextElideMode.ElideRight, max(40, label.width())
                )
            )

    def resizeEvent(self, event: object) -> None:
        super().resizeEvent(event)
        self._update_labels()

    def set_thumbnail(self, data: bytes) -> None:
        original = QPixmap()
        if data and original.loadFromData(data):
            original = original.scaled(
                ART * 2, ART * 2,
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation,
            )
            rounded = QPixmap(ART * 2, ART * 2)
            rounded.fill(Qt.GlobalColor.transparent)
            painter = QPainter(rounded)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            path = QPainterPath()
            path.addRoundedRect(QRectF(0, 0, ART * 2, ART * 2), 24, 24)
            painter.setClipPath(path)
            painter.drawPixmap(
                (ART * 2 - original.width()) // 2,
                (ART * 2 - original.height()) // 2,
                original,
            )
            painter.end()
            rounded.setDevicePixelRatio(2)
            self.art.setPixmap(rounded)
        else:
            self.art.setPixmap(icon("music", themes.GREEN, 26).pixmap(26, 26))

    def _update_progress(self) -> None:
        state = self.service.state or self.state
        if not state or self._dragging:
            return
        position = state.position_at()
        self.pos.setText(format_time(position))
        self.slider.setValue(int(position * 1000))

    def _press(self) -> None:
        self._dragging = True

    def _release(self) -> None:
        self._dragging = False
        self.service.seek(self.slider.value() / 1000)
        self._update_progress()
