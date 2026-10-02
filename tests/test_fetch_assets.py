"""fetch_assets.py with the network mocked out."""

import io
import json
import urllib.error
import zipfile

import fetch_assets as fa
import pytest


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


def test_get_retries_then_succeeds(monkeypatch):
    calls = []

    def fake_urlopen(req, timeout):
        calls.append(req.full_url)
        if len(calls) < 3:
            raise urllib.error.URLError("flaky")
        return FakeResponse(b"ok")

    monkeypatch.setattr(fa.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(fa.time, "sleep", lambda s: None)
    assert fa.get("http://x") == b"ok"
    assert len(calls) == 3


def test_get_gives_up(monkeypatch):
    def boom(req, timeout):
        raise urllib.error.URLError("down")

    monkeypatch.setattr(fa.urllib.request, "urlopen", boom)
    monkeypatch.setattr(fa.time, "sleep", lambda s: None)
    with pytest.raises(urllib.error.URLError):
        fa.get("http://x", attempts=2)


def test_save_is_idempotent(tmp_path, monkeypatch):
    monkeypatch.setattr(fa, "get", lambda url: b"data")
    dest = tmp_path / "a" / "f.bin"
    assert fa.save("u", dest) is True
    assert dest.read_bytes() == b"data"
    assert not list(dest.parent.glob("*.part"))
    monkeypatch.setattr(fa, "get", lambda url: pytest.fail("downloaded twice"))
    assert fa.save("u", dest) is False


def test_save_redownloads_empty_file(tmp_path, monkeypatch):
    dest = tmp_path / "f.bin"
    dest.write_bytes(b"")
    monkeypatch.setattr(fa, "get", lambda url: b"x")
    assert fa.save("u", dest) is True


def test_ambientcg_keeps_only_matching_texture_maps(tmp_path, monkeypatch):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for n in ("Wood_1K-JPG_Color.jpg", "Wood_1K-JPG.mtlx", "Wood_2K-JPG_Color.jpg", "Wood.png"):
            z.writestr(n, "x")
        z.writestr("Wood_1K_Color.jpg", "x")
        z.writestr("preview_1K_Roughness.txt", "x")
    monkeypatch.setattr(fa, "ASSETS", tmp_path)
    monkeypatch.setattr(fa, "get", lambda url: buf.getvalue())
    assert fa.ambientcg("Wood", "1K").endswith("downloaded")
    assert sorted(p.name for p in (tmp_path / "ambientcg" / "Wood").iterdir()) == [
        "Wood_1K_Color.jpg"
    ]
    assert fa.ambientcg("Wood", "1K").endswith("cached")


def test_polyhaven_hdri_url_selection(tmp_path, monkeypatch):
    api = json.dumps({"hdri": {"1k": {"hdr": {"url": "http://cdn/sky.hdr"}}}}).encode()
    fetched = []
    monkeypatch.setattr(fa, "ASSETS", tmp_path)
    monkeypatch.setattr(
        fa, "get", lambda url: fetched.append(url) or (api if "api." in url else b"hdr")
    )
    assert "downloaded" in fa.polyhaven_hdri("sky", "1k")
    assert (tmp_path / "polyhaven" / "hdris" / "sky_1k.hdr").read_bytes() == b"hdr"
