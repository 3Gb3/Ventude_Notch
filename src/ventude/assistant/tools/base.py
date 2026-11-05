from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

import jsonschema

from ventude.assistant.permissions import Level

Handler = Callable[[dict[str, Any]], Awaitable[Any] | Any]


class ToolError(RuntimeError):
    pass


@dataclass
class Tool:
    name: str
    description: str
    schema: dict[str, Any]
    handler: Handler
    level: Level = Level.AUTO
    destructive: bool = False

    def validate(self, args: dict[str, Any]) -> None:
        try:
            jsonschema.validate(args, self.schema)
        except jsonschema.ValidationError as exc:
            raise ToolError(f"Argumentos inválidos: {exc.message}") from exc

    def spec(self) -> dict[str, Any]:
        """Formato de function tool da Responses API."""
        return {
            "type": "function",
            "name": self.name,
            "description": self.description,
            "parameters": self.schema,
        }


def obj(props: dict[str, Any], required: list[str] | None = None) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": props,
        "required": required or [],
        "additionalProperties": False,
    }


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, *tools: Tool) -> None:
        for t in tools:
            jsonschema.Draft202012Validator.check_schema(t.schema)
            self._tools[t.name] = t

    def get(self, name: str) -> Tool:
        if name not in self._tools:
            raise ToolError(f"Ferramenta desconhecida: {name}")
        return self._tools[name]

    def all(self) -> list[Tool]:
        return list(self._tools.values())

    def specs(self) -> list[dict[str, Any]]:
        return [t.spec() for t in self._tools.values()]
