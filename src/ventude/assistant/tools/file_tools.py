from __future__ import annotations

from pathlib import Path
from typing import Any

from ventude.assistant.permissions import Level
from ventude.assistant.tools.base import Tool, ToolError, obj

MAX_READ = 200_000
BLOCKED_PARTS = {"appdata", ".ssh", ".gnupg", "ventude"}


def default_roots() -> list[Path]:
    home = Path.home()
    return [home / n for n in ("Documents", "Desktop", "Downloads") if (home / n).exists()]


class PathGuard:
    """Só permite caminhos dentro das raízes autorizadas (resolve symlinks e '..')."""

    def __init__(self, roots: list[Path]) -> None:
        self.roots = [r.resolve() for r in roots]

    def check(self, raw: str) -> Path:
        if not raw or "\x00" in raw:
            raise ToolError("Caminho inválido.")
        p = Path(raw).expanduser()
        p = p.resolve() if p.is_absolute() else (self.roots[0] / p).resolve() if self.roots else p
        root = next((r for r in self.roots if p == r or r in p.parents), None)
        if root is None:
            raise ToolError("Fora das pastas permitidas.")
        if any(part.lower() in BLOCKED_PARTS for part in p.relative_to(root).parts):
            raise ToolError("Pasta protegida.")
        return p


def file_tools(guard: PathGuard) -> list[Tool]:
    def list_dir(args: dict[str, Any]) -> Any:
        p = guard.check(args["path"])
        if not p.is_dir():
            raise ToolError("Não é uma pasta.")
        items = sorted(p.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower()))[:200]
        return [{"name": i.name, "dir": i.is_dir()} for i in items]

    def read_file(args: dict[str, Any]) -> Any:
        p = guard.check(args["path"])
        if not p.is_file():
            raise ToolError("Arquivo não encontrado.")
        if p.stat().st_size > MAX_READ:
            raise ToolError("Arquivo grande demais (limite 200 KB).")
        return p.read_text(encoding="utf-8", errors="replace")

    def write_file(args: dict[str, Any]) -> Any:
        p = guard.check(args["path"])
        if p.exists() and not args.get("overwrite"):
            raise ToolError("Arquivo já existe (use overwrite=true).")
        if not p.parent.is_dir():
            raise ToolError("Pasta de destino não existe.")
        p.write_text(args["content"], encoding="utf-8")
        return {"written": str(p), "bytes": len(args["content"].encode())}

    path = {"type": "string", "minLength": 1}
    return [
        Tool(
            "list_directory", "Lista uma pasta permitida.", obj({"path": path}, ["path"]), list_dir
        ),
        Tool(
            "read_text_file",
            "Lê um arquivo de texto permitido (até 200 KB).",
            obj({"path": path}, ["path"]),
            read_file,
        ),
        Tool(
            "write_text_file",
            "Cria (ou sobrescreve com overwrite=true) um arquivo de texto em pasta permitida.",
            obj(
                {
                    "path": path,
                    "content": {"type": "string", "maxLength": MAX_READ},
                    "overwrite": {"type": "boolean"},
                },
                ["path", "content"],
            ),
            write_file,
            Level.CONFIRM,
            destructive=True,
        ),
    ]
