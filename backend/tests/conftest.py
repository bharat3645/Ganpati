"""Shared pytest fixtures for the backend test suite.

Tests are hermetic by design: nothing here reaches out to the real network.
- The Ganesh backdrop is always loaded from the bundled local asset (no
  network involved to begin with, see app.load_local_ganesh_image).
- The logo fetch and the rembg background-removal call are monkeypatched to
  cheap local equivalents so the suite runs fast and offline, including in
  CI, without downloading rembg's ~176MB ONNX model or hitting Pexels.
"""
import base64
import io
import sys
from pathlib import Path

import pytest
from PIL import Image
from fastapi.testclient import TestClient

# Make `backend/app.py` importable as `app` regardless of the CWD pytest is
# invoked from (mirrors how run.py/uvicorn import it).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import app as app_module  # noqa: E402


@pytest.fixture()
def client():
    return TestClient(app_module.app)


def _make_png_bytes(color=(255, 0, 0), size=(32, 32)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, format="PNG")
    return buf.getvalue()


@pytest.fixture()
def tiny_photo_base64() -> str:
    """A small valid PNG as a data: URL, the same shape the frontend sends."""
    png_bytes = _make_png_bytes()
    return "data:image/png;base64," + base64.b64encode(png_bytes).decode()


@pytest.fixture()
def tiny_photo_image() -> Image.Image:
    return Image.open(io.BytesIO(_make_png_bytes()))


@pytest.fixture(autouse=True)
def _stub_slow_external_calls(monkeypatch):
    """Applied to every test automatically: replace the two things that
    would otherwise require real network / a large model download with fast
    deterministic stand-ins."""

    def _fake_fetch_image_from_url(url: str) -> Image.Image:
        # Stands in for fetching the logo image over HTTP.
        return Image.open(io.BytesIO(_make_png_bytes(color=(0, 128, 255), size=(64, 64))))

    def _fake_remove_background(image: Image.Image) -> Image.Image:
        # Skip rembg entirely (it would otherwise download an ONNX model on
        # first use); returning the input unchanged is exactly the same
        # fallback behavior app.py already uses when rembg fails.
        return image

    monkeypatch.setattr(app_module, "fetch_image_from_url", _fake_fetch_image_from_url)
    monkeypatch.setattr(app_module, "remove_background", _fake_remove_background)
