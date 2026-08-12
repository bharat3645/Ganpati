"""Tests for backend/app.py.

Run from backend/:  pytest
Run from repo root: pytest backend
"""
import base64
import io

import pytest
from PIL import Image

import app as app_module
from app import (
    GANESH_IMAGES_DB,
    LOGOS_DB,
    MAX_USER_PHOTO_BYTES,
    RateLimiter,
    _assert_public_http_url,
    decode_base64_image,
    load_local_ganesh_image,
)


# --- Basic endpoints -------------------------------------------------------

def test_root(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert resp.json()["status"] == "healthy"


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "healthy", "message": "API is running"}


def test_get_logos(client):
    resp = client.get("/api/logos")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == len(LOGOS_DB)
    for logo in data:
        assert {"id", "name", "imageUrl"} <= logo.keys()


def test_get_ganesh_images(client):
    resp = client.get("/api/ganesh-images")
    assert resp.status_code == 200
    data = resp.json()
    assert {item["id"] for item in data} == {g["id"] for g in GANESH_IMAGES_DB}
    for item in data:
        assert "name" in item
        # The URL/file itself is intentionally not exposed here -- the
        # backend serves it from local disk, it is never sent to the client.
        assert "imageUrl" not in item


# --- POST /api/generate: validation ----------------------------------------

def test_generate_missing_field_returns_422(client, tiny_photo_base64):
    resp = client.post("/api/generate", json={
        "ganeshImageId": "ganesh_1",
        "userPhotoBase64": tiny_photo_base64,
        # selectedLogoId omitted entirely
    })
    assert resp.status_code == 422


def test_generate_blank_field_returns_422(client, tiny_photo_base64):
    resp = client.post("/api/generate", json={
        "ganeshImageId": "   ",
        "userPhotoBase64": tiny_photo_base64,
        "selectedLogoId": "logo_01",
    })
    assert resp.status_code == 422


def test_generate_unknown_ganesh_id_returns_400(client, tiny_photo_base64):
    resp = client.post("/api/generate", json={
        "ganeshImageId": "ganesh_does_not_exist",
        "userPhotoBase64": tiny_photo_base64,
        "selectedLogoId": "logo_01",
    })
    assert resp.status_code == 400
    assert "Unknown ganeshImageId" in resp.json()["detail"]


def test_generate_unknown_logo_id_returns_400(client, tiny_photo_base64):
    resp = client.post("/api/generate", json={
        "ganeshImageId": "ganesh_1",
        "userPhotoBase64": tiny_photo_base64,
        "selectedLogoId": "logo_does_not_exist",
    })
    assert resp.status_code == 400
    assert "Invalid logo ID" in resp.json()["detail"]


def test_generate_invalid_base64_returns_400(client):
    resp = client.post("/api/generate", json={
        "ganeshImageId": "ganesh_1",
        "userPhotoBase64": "data:image/png;base64,not-valid-base64!!!",
        "selectedLogoId": "logo_01",
    })
    assert resp.status_code == 400


def test_generate_non_image_payload_returns_400(client):
    # Valid base64, but it doesn't decode to an actual image.
    junk = base64.b64encode(b"this is definitely not an image").decode()
    resp = client.post("/api/generate", json={
        "ganeshImageId": "ganesh_1",
        "userPhotoBase64": f"data:image/png;base64,{junk}",
        "selectedLogoId": "logo_01",
    })
    assert resp.status_code == 400


def test_generate_oversized_photo_returns_422(client):
    # Cheap oversized-payload rejection happens at the pydantic validator
    # level (before any decoding), so this is a 422, not a 400.
    huge = "A" * (MAX_USER_PHOTO_BYTES * 2 + 1)
    resp = client.post("/api/generate", json={
        "ganeshImageId": "ganesh_1",
        "userPhotoBase64": huge,
        "selectedLogoId": "logo_01",
    })
    assert resp.status_code == 422


# --- POST /api/generate: happy path -----------------------------------------

def test_generate_happy_path(client, tiny_photo_base64):
    # fetch_image_from_url and remove_background are stubbed by the autouse
    # fixture in conftest.py, so this exercises the real decode -> local
    # asset load -> composite -> (no-op AI step, HF_TOKEN unset) -> encode
    # pipeline without touching the network.
    resp = client.post("/api/generate", json={
        "ganeshImageId": "ganesh_1",
        "userPhotoBase64": tiny_photo_base64,
        "selectedLogoId": "logo_01",
    })
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["imageUrl"].startswith("data:image/png;base64,")

    # And the payload really is a decodable image.
    encoded = body["imageUrl"].split(",", 1)[1]
    img = Image.open(io.BytesIO(base64.b64decode(encoded)))
    assert img.size[0] > 0 and img.size[1] > 0


# --- decode_base64_image -----------------------------------------------------

def test_decode_base64_image_valid(tiny_photo_base64):
    img = decode_base64_image(tiny_photo_base64)
    assert img.size == (32, 32)
    assert img.format == "PNG"


def test_decode_base64_image_rejects_garbage():
    with pytest.raises(ValueError):
        decode_base64_image("not-base64-at-all!!!")


def test_decode_base64_image_rejects_non_image():
    junk = base64.b64encode(b"hello world, not an image").decode()
    with pytest.raises(ValueError):
        decode_base64_image(junk)


def test_decode_base64_image_rejects_oversized(monkeypatch):
    monkeypatch.setattr(app_module, "MAX_USER_PHOTO_BYTES", 10)
    buf = io.BytesIO()
    Image.new("RGB", (32, 32)).save(buf, format="PNG")
    encoded = base64.b64encode(buf.getvalue()).decode()
    with pytest.raises(ValueError, match="too large"):
        decode_base64_image(encoded)


# --- load_local_ganesh_image --------------------------------------------------

def test_load_local_ganesh_image_all_known_ids():
    for entry in GANESH_IMAGES_DB:
        img = load_local_ganesh_image(entry["id"])
        assert img.size[0] > 0 and img.size[1] > 0
        assert img.format in ("JPEG", "MPO")  # PIL may tag some JPEGs as MPO


def test_load_local_ganesh_image_unknown_id():
    with pytest.raises(ValueError, match="Unknown ganeshImageId"):
        load_local_ganesh_image("not_a_real_id")


# --- SSRF guard (_assert_public_http_url) ------------------------------------

@pytest.mark.parametrize("url", [
    "http://127.0.0.1/x",
    "http://localhost/x",
    "http://169.254.169.254/latest/meta-data",  # cloud metadata endpoint
    "http://10.0.0.5/x",
    "http://192.168.1.1/x",
    "http://0.0.0.0/x",
])
def test_assert_public_http_url_blocks_non_public_targets(url):
    with pytest.raises(ValueError):
        _assert_public_http_url(url)


def test_assert_public_http_url_blocks_bad_scheme():
    with pytest.raises(ValueError, match="scheme"):
        _assert_public_http_url("ftp://example.com/x")


def test_assert_public_http_url_allows_public_address(monkeypatch):
    # Avoid depending on real DNS: pretend the hostname resolves to a public IP.
    def fake_getaddrinfo(host, port):
        return [(2, 1, 6, "", ("93.184.216.34", 0))]

    monkeypatch.setattr(app_module.socket, "getaddrinfo", fake_getaddrinfo)
    # Should not raise.
    _assert_public_http_url("https://example.com/logo.png")


# --- Rate limiting on POST /api/generate ------------------------------------

def test_generate_rate_limit_returns_429_after_threshold(client, tiny_photo_base64, monkeypatch):
    # Lower the limiter's threshold for this test only; the autouse
    # _reset_rate_limiter fixture clears state before/after so this doesn't
    # leak into other tests.
    monkeypatch.setattr(app_module.generate_rate_limiter, "max_requests", 2)
    monkeypatch.setattr(app_module.generate_rate_limiter, "window_seconds", 60.0)

    payload = {
        "ganeshImageId": "ganesh_1",
        "userPhotoBase64": tiny_photo_base64,
        "selectedLogoId": "logo_01",
    }

    assert client.post("/api/generate", json=payload).status_code == 200
    assert client.post("/api/generate", json=payload).status_code == 200

    third = client.post("/api/generate", json=payload)
    assert third.status_code == 429
    assert "Retry-After" in third.headers
    assert "Rate limit exceeded" in third.json()["detail"]


def test_generate_rate_limit_is_per_client_ip(monkeypatch):
    # Two different client IPs each get their own budget.
    limiter = RateLimiter(max_requests=1, window_seconds=60.0)

    class FakeClient:
        def __init__(self, host):
            self.host = host

    class FakeRequest:
        def __init__(self, host):
            self.client = FakeClient(host)

    import asyncio

    asyncio.run(limiter(FakeRequest("1.1.1.1")))
    asyncio.run(limiter(FakeRequest("2.2.2.2")))  # different IP: not limited

    with pytest.raises(Exception):
        asyncio.run(limiter(FakeRequest("1.1.1.1")))  # same IP again: limited


def test_rate_limiter_resets_after_window_elapses(monkeypatch):
    limiter = RateLimiter(max_requests=1, window_seconds=10.0)

    class FakeClient:
        host = "9.9.9.9"

    class FakeRequest:
        client = FakeClient()

    import asyncio

    clock = {"t": 1000.0}
    monkeypatch.setattr(app_module.time, "monotonic", lambda: clock["t"])

    asyncio.run(limiter(FakeRequest()))
    with pytest.raises(Exception):
        asyncio.run(limiter(FakeRequest()))

    # Advance time past the window -- the earlier hit should age out.
    clock["t"] += 11.0
    asyncio.run(limiter(FakeRequest()))  # should not raise
