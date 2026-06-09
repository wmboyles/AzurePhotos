import pytest

from azure.core.exceptions import ResourceNotFoundError
from azure.storage.blob import ContainerClient
from datetime import datetime, timezone
from flask import Flask, Response
from io import BytesIO
from werkzeug.datastructures.file_storage import FileStorage

from src.api import photos
from tests.mocks import as_mock


def test_fullsize(app: Flask, monkeypatch: pytest.MonkeyPatch) -> None:
    photos_container_sas = "sas=photos-container-sas"
    monkeypatch.setattr(
        photos, "get_container_sas", lambda container: f"sas={container}-container-sas"
    )

    with app.app_context():
        photo_name = "photo.mp4"
        response = photos.fullsize(photo_name)

        assert isinstance(response, Response)
        assert response.status_code == 302

        expected_location = f"{app.config["blob_account_url"]}/photos/{photo_name}?{photos_container_sas}"
        assert response.location == expected_location


class TestUpload:
    @pytest.fixture(autouse=True)
    def _setup(
        self,
        app: Flask,
        monkeypatch: pytest.MonkeyPatch,
        fake_photos_container_client: ContainerClient,
        fake_thumbnails_container_client: ContainerClient,
    ) -> None:
        self.app = app
        self.photo_client = fake_photos_container_client
        self.thumbnails_client = fake_thumbnails_container_client

        monkeypatch.setattr(photos, "compute_thumbnail", lambda _: b"thumbnail-bytes")

    @staticmethod
    def make_file(
        filename: str = "photo.jpg", content: bytes = b"photo-data"
    ) -> FileStorage:
        return FileStorage(stream=BytesIO(content), filename=filename)

    def test_upload_success(self) -> None:
        filename = "photo.jpg"
        file = self.make_file(filename=filename)
        date_taken = datetime(2026, 1, 1, tzinfo=timezone.utc)

        with self.app.app_context():
            result = photos.upload(file, date_taken)

        assert result == filename
        thumbnails_client_upload_blob_mock = as_mock(self.thumbnails_client.upload_blob)
        thumbnails_client_upload_blob_mock.assert_called_once()

        thumbnail_kwargs = thumbnails_client_upload_blob_mock.call_args.kwargs
        assert thumbnail_kwargs["name"] == filename

        photo_client_upload_blob_mock = as_mock(self.photo_client.upload_blob)
        photo_client_upload_blob_mock.assert_called_once()
        photo_kwargs = photo_client_upload_blob_mock.call_args.kwargs
        assert photo_kwargs["name"] == filename

    def test_upload_secure_filename(self) -> None:
        safe_filename = "evil.mp4"
        file = self.make_file(filename=f"../../../{safe_filename}")
        date_taken = datetime(2026, 1, 1, tzinfo=timezone.utc)

        with self.app.app_context():
            result = photos.upload(file, date_taken)

        assert result == safe_filename

        video_kwargs = as_mock(self.photo_client.upload_blob).call_args.kwargs
        assert video_kwargs["name"] == safe_filename


class TestDelete:
    def test_delete_fullsize(
        self, app: Flask, fake_photos_container_client: ContainerClient
    ) -> None:
        filename = "photo.jpg"
        with app.app_context():
            photos.delete_fullsize(filename)

        as_mock(fake_photos_container_client.delete_blob).assert_called_once_with(
            filename
        )

    def test_delete_fullsize_missing_blob(
        self, app: Flask, fake_photos_container_client: ContainerClient
    ) -> None:
        fake_photos_container_client_delete_blob_mock = as_mock(
            fake_photos_container_client.delete_blob
        )
        fake_photos_container_client_delete_blob_mock.side_effect = (
            ResourceNotFoundError(message="missing")
        )

        filename = "photo.jpg"
        with app.app_context():
            photos.delete_fullsize(filename)

        fake_photos_container_client_delete_blob_mock.assert_called_once_with(filename)

    def test_delete_thumbnail(
        self, app: Flask, fake_thumbnails_container_client: ContainerClient
    ) -> None:
        filename = "photo.jpg"
        with app.app_context():
            photos.delete_thumbnail(filename)

        as_mock(fake_thumbnails_container_client.delete_blob).assert_called_once_with(
            filename
        )

    def test_delete_thumbnail_missing_blob(
        self, app: Flask, fake_thumbnails_container_client: ContainerClient
    ) -> None:
        fake_thumbnails_container_client_delete_blob_mock = as_mock(
            fake_thumbnails_container_client.delete_blob
        )
        fake_thumbnails_container_client_delete_blob_mock.side_effect = (
            ResourceNotFoundError(message="missing")
        )

        filename = "photo.jpg"
        with app.app_context():
            photos.delete_thumbnail(filename)

        fake_thumbnails_container_client_delete_blob_mock.assert_called_once_with(
            filename
        )
