import json
from types import SimpleNamespace

import pytest
from PySide6.QtCore import QEvent, QPoint, QPointF, QRect, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QApplication, QWidget

from ventude.core.config import Settings
from ventude.core.events import EventBus
from ventude.storage.database import Database
from ventude.ui.assistant_island import AssistantIsland
from ventude.ui.island_base import FloatingIsland, anchored_rect


class SampleIsland(FloatingIsland):
    def _sizes(self, expanded):
        return (600, 400) if expanded else (200, 46)


@pytest.fixture
def fake_screens(monkeypatch):
    left_area = QRect(-1920, 0, 1920, 1040)
    main_area = QRect(0, 0, 1920, 1040)
    left = SimpleNamespace(geometry=lambda: left_area, availableGeometry=lambda: left_area)
    main = SimpleNamespace(geometry=lambda: main_area, availableGeometry=lambda: main_area)
    monitors = [main, left]
    monkeypatch.setattr("ventude.ui.island_base.screens", lambda: monitors)
    monkeypatch.setattr("ventude.ui.island_base.screen_for", lambda index: monitors[index])
    monkeypatch.setattr(
        QApplication,
        "screenAt",
        lambda point: next(
            (screen for screen in monitors if screen.geometry().contains(point)), None
        ),
    )
    return monitors


def test_expanded_geometry_stays_inside_negative_monitor():
    area = QRect(-1600, -200, 1600, 860)
    rect = anchored_rect(area, 740, 470, QPoint(-20, 640))
    assert area.adjusted(8, 8, -8, -8).contains(rect)
    compact = anchored_rect(area, 216, 46, QPoint(-1500, -180))
    assert compact.x() < 0
    assert area.adjusted(8, 8, -8, -8).contains(compact)


@pytest.mark.parametrize(("x", "monitor_index"), [(-1300, 1), (400, 0)])
def test_dragged_position_roundtrips_without_moving(qapp, tmp_path, fake_screens, x, monitor_index):
    db = Database(tmp_path / "positions.db")
    settings = Settings()
    island = SampleIsland(
        settings, db, EventBus(), position_key="island_position_json", title="Test", symbol="apps"
    )
    island.expanded = True
    island.setGeometry(QRect(100, 100, 600, 400))
    start = QPointF(180, 120)
    finish = start + QPointF(x - 100, 60)
    for kind, pos, button, buttons in (
        (QEvent.Type.MouseButtonPress, start, Qt.LeftButton, Qt.LeftButton),
        (QEvent.Type.MouseMove, finish, Qt.NoButton, Qt.LeftButton),
        (QEvent.Type.MouseButtonRelease, finish, Qt.LeftButton, Qt.NoButton),
    ):
        event = QMouseEvent(kind, QPointF(80, 20), pos, button, buttons, Qt.NoModifier)
        QApplication.sendEvent(island.header, event)

    placed = QRect(x, 160, 600, 400)
    assert settings.monitor_index == monitor_index
    island.reposition()
    assert island.geometry() == placed
    assert (
        json.loads(db.load_settings().island_position_json)["x"] == placed.x() + placed.width() // 2
    )
    island.deleteLater()
    db.close()


def test_assistant_stays_on_its_monitor_when_main_is_moved(qapp, tmp_path, fake_screens):
    db = Database(tmp_path / "independent.db")
    settings = Settings()
    assistant = AssistantIsland(settings, db, EventBus(), QWidget)
    before = assistant._target_rect(False)
    # This is what dragging the main island onto monitor 2 updates.
    settings.monitor_index = 1
    after = assistant._target_rect(False)
    assert after == before
    assistant.deleteLater()
    db.close()
