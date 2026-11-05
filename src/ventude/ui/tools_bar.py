"""Compact utility controls for the main notch (color pick, OCR capture)."""

from __future__ import annotations

from PySide6.QtCore import QObject, QPoint, Signal
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextEdit,
    QToolTip,
    QVBoxLayout,
    QWidget,
)

from ventude.services.capture import (
    ColorPickOverlay,
    RegionOverlay,
    SampledColor,
    copy_image,
    copy_text,
    grab_screen,
)
from ventude.services.ocr import extract_text
from ventude.ui import themes
from ventude.ui.icons import icon, icon_button


class ToolsController(QObject):
    toast = Signal(str)
    assistant_toggle = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._overlay: QWidget | None = None
        self._ai_active = False

    def set_ai_active(self, active: bool) -> None:
        self._ai_active = active

    def pick_color(self) -> None:
        if self._overlay is not None:
            return

        def done(color: SampledColor | None) -> None:
            self._overlay = None
            if color is None:
                self.toast.emit("Seleção de cor cancelada")
                return
            copy_text(color.clipboard_text)
            self.toast.emit(f"Cor copiada · {color.hex}")

        overlay = ColorPickOverlay(done)
        self._overlay = overlay
        overlay.show()
        overlay.raise_()
        overlay.activateWindow()

    def capture_ocr(self) -> None:
        if self._overlay is not None:
            return

        def done(rect) -> None:
            self._overlay = None
            if rect is None:
                self.toast.emit("Captura cancelada")
                return
            pixmap = grab_screen(rect)
            if pixmap.isNull():
                self.toast.emit("Falha ao capturar a tela")
                return
            copy_image(pixmap)
            result = extract_text(pixmap)
            if not result.available:
                self.toast.emit("Captura copiada · OCR indisponível")
                _show_text_dialog("Texto OCR", result.text, pixmap_note=True)
                return
            if result.empty:
                self.toast.emit("Captura copiada · nenhum texto encontrado")
                return
            copy_text(result.text)
            self.toast.emit(f"Texto OCR copiado · {result.engine}")
            _show_text_dialog("Texto extraído", result.text)

        overlay = RegionOverlay(done)
        self._overlay = overlay
        overlay.show()
        overlay.raise_()
        overlay.activateWindow()


def _show_text_dialog(title: str, text: str, *, pixmap_note: bool = False) -> None:
    dialog = QDialog()
    dialog.setWindowTitle(title)
    dialog.setMinimumSize(420, 280)
    layout = QVBoxLayout(dialog)
    if pixmap_note:
        note = QLabel("A captura foi copiada para a área de transferência.")
        note.setObjectName("Muted")
        layout.addWidget(note)
    editor = QTextEdit()
    editor.setReadOnly(True)
    editor.setPlainText(text)
    layout.addWidget(editor, 1)
    row = QHBoxLayout()
    row.addStretch()
    copy_btn = QPushButton("Copiar")
    copy_btn.setObjectName("Primary")
    copy_btn.clicked.connect(lambda: copy_text(editor.toPlainText()))
    close_btn = QPushButton("Fechar")
    close_btn.clicked.connect(dialog.accept)
    row.addWidget(copy_btn)
    row.addWidget(close_btn)
    layout.addLayout(row)
    dialog.exec()


class ToolsBar(QWidget):
    """Icon strip embedded in the island header."""

    def __init__(self, controller: ToolsController, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("ToolsStrip")
        self.controller = controller
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        self.color_btn = icon_button("eyedropper", "Selecionar cor da tela", 30)
        self.ocr_btn = icon_button("scan-text", "Capturar região e extrair texto", 30)
        self.ai_btn = icon_button("sparkles", "Mostrar ou ocultar painel de IA", 30)
        self.ai_btn.setCheckable(True)

        self.color_btn.clicked.connect(controller.pick_color)
        self.ocr_btn.clicked.connect(controller.capture_ocr)
        self.ai_btn.clicked.connect(controller.assistant_toggle.emit)

        for button in (self.color_btn, self.ocr_btn, self.ai_btn):
            layout.addWidget(button)

        controller.toast.connect(self.show_toast)

    def set_ai_checked(self, checked: bool) -> None:
        self.ai_btn.setChecked(checked)
        self.ai_btn.setIcon(icon("sparkles", themes.GREEN if checked else themes.TEXT_MUTED))
        self.ai_btn.setToolTip("Ocultar painel de IA" if checked else "Mostrar painel de IA")
        self.controller.set_ai_active(checked)

    def show_toast(self, message: str) -> None:
        anchor = self.ai_btn.mapToGlobal(QPoint(0, self.ai_btn.height()))
        QToolTip.showText(anchor, message, self.ai_btn, self.ai_btn.rect(), 2600)
