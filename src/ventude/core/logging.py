from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler

from ventude.core.paths import app_data_dir


def setup_logging(level: int = logging.INFO) -> None:
    log_file = app_data_dir() / "ventude.log"
    handler = RotatingFileHandler(log_file, maxBytes=1_000_000, backupCount=3, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    root = logging.getLogger()
    root.setLevel(level)
    root.addHandler(handler)
