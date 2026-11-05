from __future__ import annotations

from collections.abc import Callable
from typing import Any

from ventude.assistant.permissions import Level
from ventude.assistant.tools.base import Tool, ToolError, obj
from ventude.core.config import Settings
from ventude.services.launcher import default_label, validate_path
from ventude.storage.database import Database

EDITABLE = {
    "collapse_delay_ms": {"type": "integer", "minimum": 0, "maximum": 10000},
    "animation_ms": {"type": "integer", "minimum": 50, "maximum": 2000},
    "clock_24h": {"type": "boolean"},
    "monitor_index": {"type": "integer", "minimum": 0},
}


def ventude_tools(
    db: Database,
    get_settings: Callable[[], Settings],
    apply_settings: Callable[[Settings], None],
    on_pinned_changed: Callable[[], None] = lambda: None,
) -> list[Tool]:
    def list_pinned(args: dict[str, Any]) -> Any:
        kinds = [args["kind"]] if args.get("kind") else ["app", "folder"]
        return [
            {"id": i.id, "kind": i.kind, "label": i.label, "path": i.path}
            for k in kinds
            for i in db.list_pinned(k)
        ]

    def pin(args: dict[str, Any]) -> Any:
        ok, msg = validate_path(args["kind"], args["path"])
        if not ok:
            raise ToolError(msg)
        item = db.add_pinned(
            args["kind"], args.get("label") or default_label(args["path"]), args["path"]
        )
        if item is None:
            raise ToolError("Já está fixado.")
        on_pinned_changed()
        return {"id": item.id, "label": item.label}

    def unpin(args: dict[str, Any]) -> Any:
        ids = {i.id for k in ("app", "folder") for i in db.list_pinned(k)}
        if args["id"] not in ids:
            raise ToolError("Item não encontrado.")
        db.remove_pinned(args["id"])
        on_pinned_changed()
        return {"removed": args["id"]}

    def update_settings(args: dict[str, Any]) -> Any:
        s = get_settings()
        data = s.to_dict() | args
        new = Settings.from_dict(data)
        apply_settings(new)
        return {k: getattr(new, k) for k in args}

    kind = {"type": "string", "enum": ["app", "folder"]}
    return [
        Tool(
            "list_pinned_apps",
            "Lista aplicativos e pastas fixados no Ventude.",
            obj({"kind": kind}),
            list_pinned,
        ),
        Tool(
            "pin_item",
            "Fixa um aplicativo (.exe/.lnk/.url/.bat/.cmd) ou uma pasta no Ventude.",
            obj(
                {
                    "kind": kind,
                    "path": {"type": "string", "minLength": 1},
                    "label": {"type": "string"},
                },
                ["kind", "path"],
            ),
            pin,
            Level.CONFIRM,
        ),
        Tool(
            "unpin_item",
            "Remove um item fixado pelo id (veja list_pinned_apps).",
            obj({"id": {"type": "integer"}}, ["id"]),
            unpin,
            Level.CONFIRM,
            destructive=True,
        ),
        Tool(
            "update_settings",
            "Altera configurações do Ventude.",
            {**obj(EDITABLE), "minProperties": 1},
            update_settings,
            Level.CONFIRM,
        ),
    ]
