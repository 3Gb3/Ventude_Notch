from ventude.services.launcher import default_label, open_path, validate_path


def test_validate_folder(tmp_path):
    assert validate_path("folder", str(tmp_path))[0]
    assert not validate_path("folder", str(tmp_path / "nope"))[0]
    assert not validate_path("folder", "")[0]


def test_validate_app(tmp_path):
    exe = tmp_path / "x.exe"
    exe.write_bytes(b"")
    txt = tmp_path / "x.txt"
    txt.write_text("")
    assert validate_path("app", str(exe))[0]
    assert not validate_path("app", str(txt))[0]
    assert not validate_path("app", str(tmp_path))[0]


def test_default_label_and_missing_open(tmp_path):
    assert default_label(r"C:\Apps\Spotify.lnk") in {"Spotify", r"C:\Apps\Spotify"}
    assert not open_path(str(tmp_path / "missing"))[0]
