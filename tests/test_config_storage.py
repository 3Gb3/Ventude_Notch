from ventude.core.config import Settings
from ventude.storage.database import Database


def test_settings_roundtrip(tmp_path):
    db = Database(tmp_path / "t.db")
    s = Settings(monitor_index=1, collapse_delay_ms=900)
    db.save_settings(s)
    db.close()
    loaded = Database(tmp_path / "t.db").load_settings()
    assert loaded.monitor_index == 1
    assert loaded.collapse_delay_ms == 900


def test_settings_sanitizes_values():
    s = Settings.from_dict({"collapse_delay_ms": -5, "animation_ms": 99999, "bogus": 1})
    assert s.collapse_delay_ms == 0
    assert s.animation_ms == 2000


def test_pinned_crud_and_order(tmp_path):
    db = Database(tmp_path / "t.db")
    a = db.add_pinned("folder", "A", str(tmp_path / "a"))
    b = db.add_pinned("folder", "B", str(tmp_path / "b"))
    assert a and b
    assert db.add_pinned("folder", "A2", str(tmp_path / "a")) is None
    db.move_pinned(b.id, -1)
    assert [i.label for i in db.list_pinned("folder")] == ["B", "A"]
    db.remove_pinned(a.id)
    assert [i.label for i in db.list_pinned("folder")] == ["B"]
    assert db.list_pinned("app") == []
