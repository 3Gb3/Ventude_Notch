"""Headful demo helper: render the redesigned notch and save PNGs."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QLabel, QVBoxLayout, QWidget

# Allow running without install.
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ventude.core.config import Settings  # noqa: E402
from ventude.core.events import EventBus  # noqa: E402
from ventude.services.media import MediaService  # noqa: E402
from ventude.storage.database import Database  # noqa: E402
from ventude.ui import themes  # noqa: E402
from ventude.ui.notch import IslandWindow  # noqa: E402


def main() -> int:
    out = Path(os.environ.get("VENTUDE_DEMO_OUT", "/cursor/stores/self/media"))
    out.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("VENTUDE_HOME", str(out / ".demo-home"))
    app = QApplication(sys.argv)
    app.setStyleSheet(themes.STYLESHEET)
    db = Database(Path(os.environ["VENTUDE_HOME"]) / "demo.db")
    island = IslandWindow(Settings(animation_ms=160), db, EventBus(), MediaService())
    island.move(80, 40)
    island.show()
    island.raise_()

    stage = {"n": 0}

    def shot(name: str) -> None:
        path = out / name
        island.grab().save(str(path), "PNG")
        print(f"saved {path}")

    def step() -> None:
        n = stage["n"]
        stage["n"] = n + 1
        if n == 0:
            shot("notch-compact.png")
            island.animate_to(True)
            QTimer.singleShot(280, step)
        elif n == 1:
            shot("notch-expanded.png")
            island.set_assistant_visible(True)
            # Fake AI companion badge for the screenshot of the toggle state.
            shot("notch-ai-toggled.png")
            QTimer.singleShot(200, step)
        elif n == 2:
            # Tiny legend card so reviewers see tool meanings without emoji.
            card = QWidget(None)
            card.setStyleSheet(
                f"background:{themes.BLACK}; color:{themes.TEXT};"
                f" border:1px solid {themes.BORDER}; border-radius:12px;"
            )
            lay = QVBoxLayout(card)
            for line in (
                "Ferramentas do notch",
                "Conta-gotas — amostrar cor da tela",
                "OCR — capturar região e extrair texto",
                "IA — mostrar ou ocultar o painel",
            ):
                label = QLabel(line)
                if line.startswith("Ferramentas"):
                    label.setObjectName("Title")
                else:
                    label.setObjectName("Muted")
                lay.addWidget(label)
            card.setFixedSize(360, 160)
            card.move(80, 520)
            card.show()

            def save_legend() -> None:
                path = out / "notch-tools-legend.png"
                card.grab().save(str(path), "PNG")
                print(f"saved {path}")

            QTimer.singleShot(80, save_legend)
            QTimer.singleShot(400, app.quit)
        else:
            app.quit()

    QTimer.singleShot(250, step)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
