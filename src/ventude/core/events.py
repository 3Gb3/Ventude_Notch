from __future__ import annotations

from PySide6.QtCore import QObject, Signal


class EventBus(QObject):
    """Barramento de eventos central entre UI e serviços."""

    settings_changed = Signal(str)
    pinned_changed = Signal()
    monitor_changed = Signal(int)
    menu_opened = Signal()
    menu_closed = Signal()
    apply_settings_requested = Signal(object)
