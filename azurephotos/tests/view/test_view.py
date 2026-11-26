import pytest

from datetime import datetime
from flask import Flask, Response
from pathlib import Path
from urllib.parse import parse_qs, urlparse
import os
from flask.testing import FlaskClient
from typing import Any

from src.view import view
from src.lib.models import media


def test_static_asset_url_changes_when_file_changes(
    app: Flask, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    asset = tmp_path / "index.js"
    asset.write_text("const example = 1;")
    monkeypatch.setattr(app, "static_folder", str(tmp_path))
    with app.test_request_context():
        first = view.static_asset_url("index.js")
        stamp = asset.stat().st_mtime_ns + 1_000_000_000
        os.utime(asset, ns=(stamp, stamp))
        second = view.static_asset_url("index.js")
    assert urlparse(first).path == "/static/index.js"
    assert first != second
    assert parse_qs(urlparse(second).query)["v"] == [str(asset.stat().st_mtime_ns)]


class TestLandingViewController:
    def test_main(self, client: FlaskClient, monkeypatch: pytest.MonkeyPatch) -> None:
        media_records: list[media.MediaRecord] = [
            media.MediaRecord(
                datetime(2026, 1, 1, 1, 1, 1), "video.mp4", media.MediaType.VIDEO
            ),
            media.MediaRecord(
                datetime(2026, 1, 1, 1, 1, 1), "photo.jpg", media.MediaType.PHOTO
            ),
        ]
        albums: list[str] = ["Album1", "Album2"]
        monkeypatch.setattr(view, "all_media", lambda: media_records)
        monkeypatch.setattr(view, "list_albums", lambda: albums)

        rendered = dict[str, str | Any]()

        def fake_renderer(template: str, **kwargs) -> str:
            rendered["template"] = template
            rendered["kwargs"] = kwargs

            return "rendered-html"

        monkeypatch.setattr(view, "render_template", fake_renderer)

        response = client.get("/")
        assert response.status_code == 200
        assert response.data == b"rendered-html"
        assert rendered["template"] == "photos.html"
        assert rendered["kwargs"] == {"medias": media_records, "albums": albums}


class TestAlbumsViewController:
    def test_albums(self, client: FlaskClient, monkeypatch: pytest.MonkeyPatch) -> None:
        album_records: list[media.MediaRecord] = [
            media.MediaRecord(
                datetime(2026, 1, 1, 1, 1, 1), "video.mp4", media.MediaType.VIDEO
            ),
            media.MediaRecord(
                datetime(2026, 1, 1, 1, 1, 1), "photo.jpg", media.MediaType.PHOTO
            ),
        ]
        albums: list[str] = ["Album1", "Album2"]
        monkeypatch.setattr(view, "list_album", lambda _: album_records)
        monkeypatch.setattr(view, "list_albums", lambda: albums)

        rendered = dict[str, str | Any]()

        def fake_renderer(template: str, **kwargs) -> str:
            rendered["template"] = template
            rendered["kwargs"] = kwargs

            return "rendered-html"

        monkeypatch.setattr(view, "render_template", fake_renderer)

        album_name = "Album1"
        response = client.get(f"/albums/{album_name}")
        assert response.status_code == 200
        assert response.data == b"rendered-html"
        assert rendered["template"] == "album.html"
        assert rendered["kwargs"] == {
            "medias": album_records,
            "albums": albums,
            "album": album_name,
        }

    def test_albums_bas_response(
        self, client: FlaskClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        bad_response = Response("Album doesn't exist", status=404)
        monkeypatch.setattr(view, "list_album", lambda _: bad_response)
        monkeypatch.setattr(view, "list_albums", lambda: [])

        response = client.get(f"/albums/missing")
        assert response.status_code == bad_response.status_code
        assert response.data == bad_response.data
