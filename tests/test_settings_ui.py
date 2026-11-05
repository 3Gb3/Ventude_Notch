from types import SimpleNamespace

from PySide6.QtCore import QRect

from ventude.core.config import Settings
from ventude.ui.pages.settings_page import SettingsPage


def test_settings_change_preserves_previous_monitor(qapp, monkeypatch):
    monitors = [
        SimpleNamespace(name=lambda: "Tela 1", geometry=lambda: QRect(0, 0, 1920, 1080)),
        SimpleNamespace(name=lambda: "Tela 2", geometry=lambda: QRect(1920, 0, 1920, 1080)),
    ]
    monkeypatch.setattr("ventude.ui.pages.settings_page.screens", lambda: monitors)
    original = Settings(monitor_index=0, weather_city_json='{"name":"Recife"}')
    changes = []
    page = SettingsPage(original, changes.append)

    page.monitor.setCurrentIndex(1)

    assert len(changes) == 1
    assert changes[0].monitor_index == 1
    assert original.monitor_index == 0
    assert changes[0].weather_city_json == original.weather_city_json
    page.sync(original)
    assert len(changes) == 1
    assert page.monitor.currentIndex() == 0
    page.close()
