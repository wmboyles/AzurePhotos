import pytest

from datetime import datetime
from flask import Flask, Response
from flask.testing import FlaskClient
from jinja2 import FileSystemLoader
from pathlib import Path
from typing import Any

from src.view import view
from src.lib.models import media


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

    def test_mobile_navigation_and_shared_album_picker(
        self, app: Flask, client: FlaskClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        app.jinja_loader = FileSystemLoader(str(Path(__file__).resolve().parents[2] / "templates"))
        records = [
            media.MediaRecord(datetime(2026, 1, 1), filename, media.MediaType.PHOTO)
            for filename in ["first.jpg", "second.jpg"]
        ]
        monkeypatch.setattr(view, "all_media", lambda: records)
        monkeypatch.setattr(view, "list_albums", lambda: ["Family & Trips"])

        response = client.get("/")
        html = response.get_data(as_text=True)

        assert response.status_code == 200
        assert 'href="#photos" data-view="photos"' in html
        assert 'href="#albums" data-view="albums"' in html
        assert 'href="#upload" data-view="upload"' in html
        assert html.count('data-target-album="Family &amp; Trips"') == 2
        assert html.count('class="photo-open"') == len(records)
        assert 'id="deleteSelectedBtn" disabled>\n      Delete' in html


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

    @pytest.mark.parametrize("has_media", [True, False])
    def test_mobile_album_navigation_and_remove_action(
        self, app: Flask, client: FlaskClient, monkeypatch: pytest.MonkeyPatch, has_media: bool
    ) -> None:
        app.jinja_loader = FileSystemLoader(str(Path(__file__).resolve().parents[2] / "templates"))
        records = [
            media.MediaRecord(datetime(2026, 1, 1), "photo.jpg", media.MediaType.PHOTO)
        ] if has_media else []
        monkeypatch.setattr(view, "list_album", lambda _: records)
        monkeypatch.setattr(view, "list_albums", lambda: ["Family", "Trips"])

        response = client.get("/albums/Family")
        html = response.get_data(as_text=True)

        assert response.status_code == 200
        assert 'href="/#photos" data-view="photos"' in html
        assert 'href="/#albums" data-view="albums"' in html
        assert 'href="#upload" data-view="upload"' in html
        assert 'data-target-album="Family"' not in html
        assert 'data-target-album="Trips"' in html
        assert 'id="deleteSelectedBtn" disabled>\n      Remove' in html
        assert 'id="mediaEmptyState" hidden' in html if has_media else 'id="mediaEmptyState" >' in html

    def test_albums_bas_response(
        self, client: FlaskClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        bad_response = Response("Album doesn't exist", status=404)
        monkeypatch.setattr(view, "list_album", lambda _: bad_response)
        monkeypatch.setattr(view, "list_albums", lambda: [])

        response = client.get(f"/albums/missing")
        assert response.status_code == bad_response.status_code
        assert response.data == bad_response.data
