"""Extract text from screenshots via Tesseract or Windows OCR when available."""

from __future__ import annotations

import logging
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtGui import QImage, QPixmap

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class OcrResult:
    text: str
    engine: str
    available: bool

    @property
    def empty(self) -> bool:
        return not self.text.strip()


def extract_text(pixmap: QPixmap) -> OcrResult:
    if pixmap.isNull():
        return OcrResult("", "none", False)
    if sys.platform == "win32":
        result = _windows_ocr(pixmap)
        if result is not None:
            return result
    result = _tesseract_ocr(pixmap)
    if result is not None:
        return result
    return OcrResult(
        "OCR indisponível neste ambiente. "
        "No Windows a OCR nativa é usada quando disponível; "
        "caso contrário instale o Tesseract (tesseract-ocr).",
        "none",
        False,
    )


def _save_temp_png(pixmap: QPixmap) -> Path:
    import os

    handle, name = tempfile.mkstemp(suffix=".png")
    os.close(handle)
    path = Path(name)
    pixmap.save(str(path), "PNG")
    return path


def _tesseract_ocr(pixmap: QPixmap) -> OcrResult | None:
    binary = shutil.which("tesseract")
    if not binary:
        return None
    image_path = _save_temp_png(pixmap)
    try:
        completed = subprocess.run(  # noqa: S603
            [binary, str(image_path), "stdout", "-l", "por+eng", "--psm", "6"],
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
        text = (completed.stdout or "").strip()
        if completed.returncode != 0 and not text:
            log.warning("tesseract falhou: %s", completed.stderr)
            return OcrResult("", "tesseract", True)
        return OcrResult(text, "tesseract", True)
    except (OSError, subprocess.SubprocessError) as exc:
        log.warning("tesseract indisponível: %s", exc)
        return None
    finally:
        image_path.unlink(missing_ok=True)


def _windows_ocr(pixmap: QPixmap) -> OcrResult | None:
    """Best-effort Windows.Media.Ocr via WinRT; returns None to fall through."""
    try:
        import asyncio

        from winrt.windows.graphics.imaging import BitmapDecoder
        from winrt.windows.media.ocr import OcrEngine
        from winrt.windows.storage.streams import DataWriter, InMemoryRandomAccessStream
    except Exception:  # noqa: BLE001
        return None

    image = pixmap.toImage().convertToFormat(QImage.Format.Format_RGBA8888)
    path = _save_temp_png(QPixmap.fromImage(image))

    async def run() -> OcrResult:
        engine = OcrEngine.try_create_from_user_profile_languages()
        if engine is None:
            return OcrResult("", "windows", False)
        data = path.read_bytes()
        stream = InMemoryRandomAccessStream()
        writer = DataWriter(stream)
        writer.write_bytes(list(data))
        await writer.store_async()
        await writer.flush_async()
        stream.seek(0)
        decoder = await BitmapDecoder.create_async(stream)
        bitmap = await decoder.get_software_bitmap_async()
        result = await engine.recognize_async(bitmap)
        lines = [line.text for line in result.lines]
        return OcrResult("\n".join(lines).strip(), "windows", True)

    try:
        return asyncio.run(run())
    except Exception:  # noqa: BLE001
        log.exception("Windows OCR falhou")
        return None
    finally:
        path.unlink(missing_ok=True)
