from PySide6.QtCore import QPoint, QRect
from PySide6.QtGui import QColor, QImage, QPixmap

from ventude.core.config import Settings
from ventude.core.events import EventBus
from ventude.services.capture import SampledColor, copy_text
from ventude.services.media import MediaService
from ventude.services.ocr import extract_text
from ventude.storage.database import Database
from ventude.ui.notch import IslandWindow


def test_sampled_color_clipboard_text():
    sample = SampledColor(hex="#6EE7B7", rgb=(110, 231, 183))
    assert "6EE7B7" in sample.clipboard_text
    assert "110" in sample.clipboard_text


def test_ocr_empty_pixmap(qapp):
    result = extract_text(QPixmap())
    assert not result.available
    assert result.engine == "none"


def test_ocr_on_blank_image_falls_through(qapp):
    image = QImage(64, 32, QImage.Format.Format_RGB32)
    image.fill(QColor("white"))
    result = extract_text(QPixmap.fromImage(image))
    # Either tesseract ran (available) or stub message (unavailable).
    assert result.engine in {"tesseract", "windows", "none"}


def test_island_tools_and_ai_button(qapp, tmp_path):
    island = IslandWindow(
        Settings(animation_ms=50), Database(tmp_path / "tools.db"), EventBus(), MediaService()
    )
    assert island.tools_bar.color_btn.toolTip()
    assert island.tools_bar.ocr_btn.toolTip()
    assert island.tools_bar.ai_btn.isCheckable()
    assert not island.tools_bar.ai_btn.isChecked()
    island.set_assistant_visible(True)
    assert island.tools_bar.ai_btn.isChecked()
    island.set_assistant_visible(False)
    assert not island.tools_bar.ai_btn.isChecked()
    island.deleteLater()


def test_copy_text_roundtrip(qapp):
    copy_text("#ABC123")
    from PySide6.QtWidgets import QApplication

    assert QApplication.clipboard().text() == "#ABC123"


def test_region_geometry_helpers():
    rect = QRect(QPoint(10, 10), QPoint(40, 50)).normalized()
    assert rect.width() == 31
    assert rect.height() == 41
