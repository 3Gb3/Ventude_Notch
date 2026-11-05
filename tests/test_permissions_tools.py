import asyncio
import sqlite3

import pytest

from ventude.assistant.permissions import Level, PermissionManager
from ventude.assistant.tools.base import ToolError, ToolRegistry
from ventude.assistant.tools.file_tools import PathGuard, file_tools
from ventude.assistant.tools.system_tools import system_tools
from ventude.assistant.tools.ventude_tools import ventude_tools
from ventude.core.config import Settings
from ventude.storage.database import Database


def pm(answer=None):
    calls = []

    async def approver(tool, args, summary):
        calls.append(tool)
        return bool(answer)

    return PermissionManager(
        sqlite3.connect(":memory:"), approver if answer is not None else None
    ), calls


def test_levels_and_audit():
    m, calls = pm(answer=True)
    assert asyncio.run(m.authorize("a", {}, Level.AUTO, False, "a"))
    assert asyncio.run(m.authorize("b", {}, Level.CONFIRM, False, "b")) and calls == ["b"]
    m.overrides["c"] = Level.DENY
    assert not asyncio.run(m.authorize("c", {}, Level.AUTO, False, "c"))
    stages = [s for _t, s, _d in reversed(m.history())]
    assert stages == ["requested", "approved", "requested", "approved", "requested", "denied"]


def test_destructive_always_confirms():
    m, calls = pm(answer=False)
    assert m.level_for("x", Level.AUTO, True) == Level.CONFIRM
    assert not asyncio.run(m.authorize("x", {}, Level.AUTO, True, "x")) and calls == ["x"]


def test_confirm_without_approver_denies():
    m, _ = pm()
    assert not asyncio.run(m.authorize("x", {}, Level.CONFIRM, False, "x"))


def test_path_guard(tmp_path):
    root = tmp_path / "Docs"
    root.mkdir()
    g = PathGuard([root])
    assert g.check(str(root / "a.txt")) == (root / "a.txt").resolve()
    for bad in (str(tmp_path / "x.txt"), str(root / ".." / "x.txt"), "", "a\x00b"):
        with pytest.raises(ToolError):
            g.check(bad)
    with pytest.raises(ToolError):
        g.check(str(root / "AppData" / "x"))


def test_file_tools(tmp_path):
    reg = ToolRegistry()
    reg.register(*file_tools(PathGuard([tmp_path])))
    w = reg.get("write_text_file")
    assert w.destructive and w.level == Level.CONFIRM
    w.handler({"path": str(tmp_path / "n.txt"), "content": "oi"})
    assert reg.get("read_text_file").handler({"path": str(tmp_path / "n.txt")}) == "oi"
    with pytest.raises(ToolError):
        w.handler({"path": str(tmp_path / "n.txt"), "content": "x"})
    with pytest.raises(ToolError):
        w.validate({"path": "x"})  # falta content
    assert reg.get("list_directory").handler({"path": str(tmp_path)})[0]["name"] == "n.txt"


def test_system_info_is_safe():
    info = system_tools()[0].handler({})
    assert "os" in info and not any(k in info for k in ("user", "env", "ip"))


def test_ventude_tools(tmp_path):
    db = Database(tmp_path / "v.db")
    state = {"s": Settings()}
    changed = []
    tools = {
        t.name: t
        for t in ventude_tools(
            db, lambda: state["s"], lambda s: state.update(s=s), lambda: changed.append(1)
        )
    }
    tools["pin_item"].handler({"kind": "folder", "path": str(tmp_path)})
    listed = tools["list_pinned_apps"].handler({})
    assert listed[0]["path"] == str(tmp_path) and changed
    with pytest.raises(ToolError):
        tools["pin_item"].handler({"kind": "folder", "path": str(tmp_path / "missing")})
    tools["update_settings"].validate({"collapse_delay_ms": 900})
    with pytest.raises(ToolError):
        tools["update_settings"].validate({"collapse_delay_ms": -1})
    with pytest.raises(ToolError):
        tools["update_settings"].validate({})
    tools["update_settings"].handler({"collapse_delay_ms": 900})
    assert state["s"].collapse_delay_ms == 900
    assert tools["unpin_item"].destructive
    tools["unpin_item"].handler({"id": listed[0]["id"]})
    assert tools["list_pinned_apps"].handler({}) == []
