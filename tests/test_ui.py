from PySide6.QtCore import QRect

from ventude.core.config import Settings
from ventude.core.events import EventBus
from ventude.services.media import MediaService
from ventude.services.monitors import top_center_rect
from ventude.storage.database import Database


def test_top_center_rect():
    r = top_center_rect(QRect(100, 0, 1000, 800), 200, 40, 8)
    assert r == QRect(500, 8, 200, 40)


def test_island_builds_and_expands(qapp, tmp_path):
    from PySide6.QtCore import Qt

    from ventude.ui.notch import TABS, IslandWindow

    island = IslandWindow(
        Settings(animation_ms=50), Database(tmp_path / "u.db"), EventBus(), MediaService()
    )
    assert island.windowFlags() & Qt.WindowType.Tool
    assert island.stack.count() == len(TABS)
    compact = island.geometry()
    assert compact.width() == island._target_rect(False).width()
    island.animate_to(True)
    island.anim.setCurrentTime(island.anim.duration())
    assert island.geometry().height() > compact.height()
    island.bus.menu_opened.emit()
    island._try_collapse()
    assert island.expanded  # não recolhe com menu aberto
