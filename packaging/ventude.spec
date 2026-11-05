# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path

from PyInstaller.utils.hooks import collect_all, collect_submodules

ROOT = Path(SPECPATH).resolve().parent
UI_ASSETS = ROOT / "src" / "ventude" / "ui" / "assets"

datas, binaries, hidden = [], [], []
for pkg in (
    "winrt",
    "jsonschema",
    "jsonschema_specifications",
    "referencing",
    "rpds",
    "jwt",
    "cryptography",
    "httpx",
    "httpcore",
    "anyio",
    "h11",
    "certifi",
    "idna",
):
    try:
        d, b, h = collect_all(pkg)
        datas += d
        binaries += b
        hidden += h
    except Exception:
        pass

# Signal Bezel fonts + Streamline icons (Path(__file__)/assets in frozen app).
if UI_ASSETS.is_dir():
    datas.append((str(UI_ASSETS), "ventude/ui/assets"))

hidden += collect_submodules("ventude")
hidden += [
    "ventude",
    "ventude.app",
    "ventude.__main__",
    "winrt.windows.media.control",
    "winrt.windows.storage.streams",
    "winrt.windows.foundation",
    "winrt.windows.foundation.collections",
    "winrt.windows.media",
]

a = Analysis(
    ["../src/ventude/__main__.py"],
    pathex=["../src"],
    binaries=binaries,
    datas=datas,
    hiddenimports=sorted(set(hidden)),
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
# Qt uses the unversioned ICU API provided by Windows. A private ICU from a
# program on the build machine's PATH can have the same DLL name but a different ABI.
a.binaries = [item for item in a.binaries if not (
    Path(item[0]).name.lower() == "icuuc.dll"
    or Path(item[0]).name.lower().startswith("icudt")
)]
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Ventude",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="Ventude",
)
