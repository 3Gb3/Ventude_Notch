from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ventude.core.config import Settings
from ventude.services.monitors import screens
from ventude.ui import themes
from ventude.ui.icons import icon


class SettingsPage(QWidget):
    quit_requested = Signal()
    reset_positions_requested = Signal()

    def __init__(self, settings: Settings, on_change: Callable[[Settings], None]) -> None:
        super().__init__()
        self.settings, self.on_change = settings, on_change
        root = QVBoxLayout(self)
        root.setContentsMargins(4, 2, 4, 4)
        root.setSpacing(12)

        heading = QHBoxLayout()
        title = QLabel("Preferências")
        title.setObjectName("Title")
        saved = QLabel("Salvo automaticamente")
        saved.setObjectName("Muted")
        heading.addWidget(title)
        heading.addStretch()
        heading.addWidget(saved)
        root.addLayout(heading)

        card = QFrame()
        card.setObjectName("Card")
        form = QGridLayout(card)
        form.setContentsMargins(16, 12, 16, 12)
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(12)
        self.monitor = QComboBox()
        self.monitor.setAccessibleName("Monitor da ilha principal")
        self._refresh_monitors(settings.monitor_index)
        self.delay = QSpinBox(minimum=0, maximum=10_000, singleStep=100, suffix=" ms")
        self.delay.setValue(settings.collapse_delay_ms)
        self.delay.setAccessibleName("Tempo antes de recolher a ilha")
        self.anim = QSpinBox(minimum=50, maximum=2_000, singleStep=10, suffix=" ms")
        self.anim.setValue(settings.animation_ms)
        self.anim.setAccessibleName("Duração da animação")
        self.clock = QCheckBox("Relógio de 24 horas")
        self.clock.setChecked(settings.clock_24h)
        form.addWidget(QLabel("Monitor"), 0, 0)
        form.addWidget(self.monitor, 0, 1, 1, 3)
        form.addWidget(QLabel("Recolher após"), 1, 0)
        form.addWidget(self.delay, 1, 1)
        form.addWidget(QLabel("Animação"), 1, 2)
        form.addWidget(self.anim, 1, 3)
        form.addWidget(self.clock, 2, 0, 1, 4)
        form.setColumnStretch(1, 1)
        form.setColumnStretch(3, 1)
        root.addWidget(card)

        hint = QLabel("Arraste o cabeçalho de cada ilha para movê-la, inclusive entre monitores.")
        hint.setObjectName("Muted")
        hint.setWordWrap(True)
        root.addWidget(hint)
        root.addStretch()

        actions = QHBoxLayout()
        self.reset_positions_btn = QPushButton("Restaurar posições")
        self.reset_positions_btn.setIcon(icon("refresh", themes.TEXT_MUTED))
        self.reset_positions_btn.setToolTip("Reposicionar as duas ilhas no monitor selecionado")
        self.reset_positions_btn.clicked.connect(
            lambda _checked=False: self.reset_positions_requested.emit()
        )
        self.quit_btn = QPushButton("Sair do Ventude")
        self.quit_btn.setObjectName("Danger")
        self.quit_btn.setIcon(icon("power", themes.DANGER))
        self.quit_btn.setToolTip("Fechar o aplicativo e as duas ilhas")
        self.quit_btn.clicked.connect(lambda _checked=False: self.quit_requested.emit())
        for button in (self.reset_positions_btn, self.quit_btn):
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setMinimumHeight(36)
        actions.addWidget(self.reset_positions_btn)
        actions.addStretch()
        actions.addWidget(self.quit_btn)
        root.addLayout(actions)

        self.monitor.currentIndexChanged.connect(self._apply)
        self.delay.valueChanged.connect(self._apply)
        self.anim.valueChanged.connect(self._apply)
        self.clock.toggled.connect(self._apply)

    def _refresh_monitors(self, index: int) -> None:
        blocked = self.monitor.blockSignals(True)
        self.monitor.clear()
        for i, screen in enumerate(screens()):
            geometry = screen.geometry()
            self.monitor.addItem(
                f"{i + 1} · {screen.name()} · {geometry.width()} × {geometry.height()}"
            )
        self.monitor.setCurrentIndex(min(index, self.monitor.count() - 1))
        self.monitor.blockSignals(blocked)

    def sync(self, s: Settings) -> None:
        self.settings = s
        widgets = (self.monitor, self.delay, self.anim, self.clock)
        blocked = [widget.blockSignals(True) for widget in widgets]
        self._refresh_monitors(s.monitor_index)
        self.delay.setValue(s.collapse_delay_ms)
        self.anim.setValue(s.animation_ms)
        self.clock.setChecked(s.clock_24h)
        for widget, previous in zip(widgets, blocked, strict=True):
            widget.blockSignals(previous)

    def set_monitor(self, index: int) -> None:
        self._refresh_monitors(index)

    def _apply(self) -> None:
        # Keep the previous settings intact so consumers can detect monitor changes.
        updated = Settings.from_dict(self.settings.to_dict())
        updated.monitor_index = max(0, self.monitor.currentIndex())
        updated.collapse_delay_ms = self.delay.value()
        updated.animation_ms = self.anim.value()
        updated.clock_24h = self.clock.isChecked()
        self.settings = updated
        self.on_change(updated)
