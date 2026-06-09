from urllib import response

import pytest

from flask import Flask
from werkzeug.wrappers.response import Response

from src.api import crud_controller, photos, videos
from src.lib.models.media import MediaType


@pytest.mark.parametrize("filename", ("photo.jpg", "video.mp4"))
def test_thumbnail(
    app: Flask, monkeypatch: pytest.MonkeyPatch, filename: str
) -> None:
    thumbnails_container_sas = "sas=thumbnails-container-sas"
    monkeypatch.setattr(
        crud_controller,
        "get_container_sas",
        lambda container: f"sas={container}-container-sas",
    )

    with app.app_context():
        response = crud_controller.thumbnail(filename=filename)

    assert isinstance(response, Response)
    assert response.status_code == 302

    expected_filename = filename
    if MediaType.from_file_extension(filename) == MediaType.VIDEO:
        expected_filename += ".webp"
    expected_location = f"{app.config["blob_account_url"]}/thumbnails/{expected_filename}?{thumbnails_container_sas}"
    assert response.location == expected_location

def test_thumbnail_unknown_media_type(app: Flask) -> None:
    filename = "unknown_extension.idk"
    with app.app_context():
        response = crud_controller.thumbnail(filename)

    assert isinstance(response, Response)
    assert response.status_code == 404
    assert response.content_type == "text/plain; charset=utf-8"
    response_text = response.get_data(as_text=True)
    assert response_text.startswith("Unrecognized media_type")
    assert response_text.endswith(f"{filename=}")

def test_fullsize_photo(app: Flask, monkeypatch: pytest.MonkeyPatch) -> None:
    photos_container_sas = "sas=photos-container-sas"
    monkeypatch.setattr(
        photos,
        "get_container_sas",
        lambda container: f"sas={container}-container-sas",
    )

    filename = "photo.jpg"
    with app.app_context():
        response = crud_controller.fullsize(filename=filename)

    assert isinstance(response, Response)
    assert response.status_code == 302

    expected_location = f"{app.config["blob_account_url"]}/photos/{filename}?{photos_container_sas}"
    assert response.location == expected_location

def test_fullsize_video(app: Flask, monkeypatch: pytest.MonkeyPatch) -> None:
    videos_container_sas = "sas=videos-container-sas"
    monkeypatch.setattr(
        videos,
        "get_container_sas",
        lambda container: f"sas={container}-container-sas",
    )

    filename = "video.mp4"
    with app.app_context():
        response = crud_controller.fullsize(filename=filename)

    assert isinstance(response, Response)
    assert response.status_code == 302

    expected_location = f"{app.config["blob_account_url"]}/videos/{filename}?{videos_container_sas}"
    assert response.location == expected_location

def test_fullsize_unknown_media_type(app: Flask) -> None:
    filename = "unknown_extension.idk"
    with app.app_context():
        response = crud_controller.fullsize(filename)

    assert isinstance(response, Response)
    assert response.status_code == 404
    assert response.content_type == "text/plain; charset=utf-8"
    response_text = response.get_data(as_text=True)
    assert response_text.startswith("Unrecognized media_type")
    assert response_text.endswith(f"{filename=}")
