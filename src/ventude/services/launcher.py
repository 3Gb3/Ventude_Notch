from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

log = logging.getLogger(__name__)

APP_SUFFIXES = {".exe", ".lnk", ".url", ".bat", ".cmd", ".appref-ms"}


def validate_path(kind: str, raw: str) -> tuple[bool, str]:
    """Retorna (ok, mensagem). kind = 'app' ou 'folder'."""
    if not raw or not raw.strip():
        return False, "Caminho vazio."
    p = Path(raw.strip().strip('"'))
    if not p.exists():
        return False, "Caminho não encontrado."
    if kind == "folder":
        return (True, "") if p.is_dir() else (False, "Não é uma pasta.")
    if kind == "app":
        if not p.is_file():
            return False, "Não é um arquivo."
        if p.suffix.lower() not in APP_SUFFIXES:
            return False, "Tipo não suportado (use .exe, .lnk, .url, .bat ou .cmd)."
        return True, ""
    return False, "Tipo desconhecido."


def default_label(path: str) -> str:
    p = Path(path)
    return p.stem if p.suffix else (p.name or str(p))


def open_path(path: str) -> tuple[bool, str]:
    if not Path(path).exists():
        return False, "O caminho não existe mais."
    try:
        if sys.platform == "win32":
            os.startfile(path)  # type: ignore[attr-defined]
        else:  # pragma: no cover
            import subprocess

            subprocess.Popen(["xdg-open", path])
    except OSError as exc:
        log.exception("Falha ao abrir %s", path)
        return False, str(exc)
    return True, ""
