from __future__ import annotations

import os
from pathlib import Path


def app_data_dir() -> Path:
    """Pasta de dados do app (%APPDATA%\\Ventude). VENTUDE_HOME sobrescreve (testes)."""
    override = os.environ.get("VENTUDE_HOME")
    if override:
        base = Path(override)
    else:
        appdata = os.environ.get("APPDATA")
        base = Path(appdata) / "Ventude" if appdata else Path.home() / ".ventude"
    base.mkdir(parents=True, exist_ok=True)
    return base
