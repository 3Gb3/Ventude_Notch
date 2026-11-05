"""Armazenamento de credenciais protegido com DPAPI do Windows (ctypes).

Nada é salvo em texto puro e nenhum token vai para logs.
"""

from __future__ import annotations

import ctypes
import json
import os
import sys
import tempfile
import uuid
from ctypes import wintypes
from pathlib import Path
from typing import Any, Protocol


class Protector(Protocol):
    def protect(self, data: bytes) -> bytes: ...
    def unprotect(self, data: bytes) -> bytes: ...


class _Blob(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]


class DpapiProtector:
    """CryptProtectData/CryptUnprotectData com escopo do usuário atual."""

    ENTROPY = b"Ventude.v1"

    def __init__(self) -> None:
        if sys.platform != "win32":
            raise OSError("DPAPI só existe no Windows")
        self._crypt32 = ctypes.windll.crypt32  # type: ignore[attr-defined]
        self._kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]

    @staticmethod
    def _blob(data: bytes) -> tuple[_Blob, Any]:
        buf = ctypes.create_string_buffer(data, len(data))
        return _Blob(len(data), ctypes.cast(buf, ctypes.POINTER(ctypes.c_char))), buf

    def _call(self, fn: Any, data: bytes) -> bytes:
        inp, _keep = self._blob(data)
        ent, _keep2 = self._blob(self.ENTROPY)
        out = _Blob()
        if not fn(ctypes.byref(inp), None, ctypes.byref(ent), None, None, 0x1, ctypes.byref(out)):
            raise OSError("Falha na DPAPI")
        try:
            return ctypes.string_at(out.pbData, out.cbData)
        finally:
            self._kernel32.LocalFree(out.pbData)

    def protect(self, data: bytes) -> bytes:
        return self._call(self._crypt32.CryptProtectData, data)

    def unprotect(self, data: bytes) -> bytes:
        return self._call(self._crypt32.CryptUnprotectData, data)


class TokenStore:
    """Guarda um dicionário JSON cifrado em um arquivo (escrita atômica)."""

    def __init__(self, path: Path, protector: Protector | None = None) -> None:
        self.path = path
        self._protector = protector or DpapiProtector()

    def _load(self) -> dict[str, Any]:
        if not self.path.exists():
            return {}
        try:
            return json.loads(self._protector.unprotect(self.path.read_bytes()))
        except (OSError, ValueError):
            return {}

    def _save(self, data: dict[str, Any]) -> None:
        blob = self._protector.protect(json.dumps(data).encode())
        fd, tmp = tempfile.mkstemp(dir=self.path.parent, prefix=".cred-")
        with os.fdopen(fd, "wb") as fh:
            fh.write(blob)
        os.replace(tmp, self.path)

    def get(self, key: str) -> Any:
        return self._load().get(key)

    def set(self, key: str, value: Any) -> None:
        data = self._load()
        data[key] = value
        self._save(data)

    def delete(self, key: str) -> None:
        data = self._load()
        if data.pop(key, None) is not None:
            self._save(data)

    def host_id(self) -> str:
        """ext_agent_host_id estável (urn:uuid), criado antes do 1º login."""
        hid = self.get("ext_agent_host_id")
        if not hid:
            hid = f"urn:uuid:{uuid.uuid4()}"
            self.set("ext_agent_host_id", hid)
        return str(hid)
