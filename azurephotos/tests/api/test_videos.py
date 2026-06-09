import pytest

from azure.core.exceptions import ResourceNotFoundError
from azure.storage.blob import ContainerClient
from datetime import datetime, timezone
from flask import Flask, Response
from io import BytesIO
from werkzeug.datastructures.file_storage import FileStorage

from src.api import videos
from tests.mocks import as_mock


def test_fullsize(app: Flask, monkeypatch: pytest.MonkeyPatch) -> None:
    videos_container_sas = "sas=videos-container-sas"
    monkeypatch.setattr(
        videos, "get_container_sas", lambda container: f"sas={container}-container-sas"
    )

    with app.app_context():
        video_name = "video.mp4"
        response = videos.fullsize(video_name)

        assert isinstance(response, Response)
        assert response.status_code == 302

        expected_location = f"{app.config["blob_account_url"]}/videos/{video_name}?{videos_container_sas}"
        assert response.location == expected_location


class TestUpload:
    @pytest.fixture(autouse=True)
    def _setup(
        self,
        app: Flask,
        monkeypatch: pytest.MonkeyPatch,
        fake_videos_container_client: ContainerClient,
        fake_thumbnails_container_client: ContainerClient,
    ) -> None:
        self.app = app
        self.video_client = fake_videos_container_client
        self.thumbnails_client = fake_thumbnails_container_client

        monkeypatch.setattr(
            videos, "compute_thumbnail", lambda _, __: b"thumbnail-bytes"
        )

    @staticmethod
    def make_file(
        filename: str = "video.mp4", content: bytes = b"video-data"
    ) -> FileStorage:
        return FileStorage(stream=BytesIO(content), filename=filename)

    def test_upload_success(self) -> None:
        filename = "video.mp4"
        file = self.make_file(filename=filename)
        date_taken = datetime(2026, 1, 1, tzinfo=timezone.utc)

        with self.app.app_context():
            result = videos.upload(file, date_taken)

        assert result == filename
        thumbnails_client_upload_blob_mock = as_mock(self.thumbnails_client.upload_blob)
        thumbnails_client_upload_blob_mock.assert_called_once()

        thumbnail_kwargs = thumbnails_client_upload_blob_mock.call_args.kwargs
        assert thumbnail_kwargs["metadata"] == {"lastModified": date_taken.isoformat()}

        video_client_upload_blob_mock = as_mock(self.video_client.upload_blob)
        video_client_upload_blob_mock.assert_called_once()
        video_kwargs = video_client_upload_blob_mock.call_args.kwargs
        assert video_kwargs["name"] == filename

    def test_upload_secure_filename(self) -> None:
        safe_filename = "evil.mp4"
        file = self.make_file(filename=f"../../../{safe_filename}")
        date_taken = datetime(2026, 1, 1, tzinfo=timezone.utc)

        with self.app.app_context():
            result = videos.upload(file, date_taken)

        assert result == safe_filename

        video_kwargs = as_mock(self.video_client.upload_blob).call_args.kwargs
        assert video_kwargs["name"] == safe_filename

    def test_upload_failure_tempfile_clenup(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        removed = []
        monkeypatch.setattr(videos.os, "remove", lambda path: removed.append(path))

        as_mock(self.video_client.upload_blob).side_effect = RuntimeError(
            "upload failed"
        )

        file = self.make_file()
        date_taken = datetime(2026, 1, 1, tzinfo=timezone.utc)
        with self.app.app_context():
            with pytest.raises(RuntimeError, match="upload failed"):
                videos.upload(file, date_taken)

        assert len(removed) == 1

    def test_upload_failure_os_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def fake_remove(path: str):
            raise OSError("Fake OS Error")

        monkeypatch.setattr(videos.os, "remove", fake_remove)

        filename = "video.mp4"
        file = self.make_file(filename=filename)
        date_taken = datetime(2026, 1, 1, tzinfo=timezone.utc)
        with self.app.app_context():
            result = videos.upload(file, date_taken)

        assert result == filename


class TestDelete:
    def test_delete_fullsize(
        self, app: Flask, fake_videos_container_client: ContainerClient
    ) -> None:
        filename = "video.mp4"
        with app.app_context():
            videos.delete_fullsize(filename)

        as_mock(fake_videos_container_client.delete_blob).assert_called_once_with(
            filename
        )

    def test_delete_fullsize_missing_blob(
        self, app: Flask, fake_videos_container_client: ContainerClient
    ) -> None:
        fake_videos_container_client_delete_blob_mock = as_mock(
            fake_videos_container_client.delete_blob
        )
        fake_videos_container_client_delete_blob_mock.side_effect = (
            ResourceNotFoundError(message="missing")
        )

        filename = "video.mp4"
        with app.app_context():
            videos.delete_fullsize(filename)

        fake_videos_container_client_delete_blob_mock.assert_called_once_with(filename)

    def test_delete_thumbnail(
        self, app: Flask, fake_thumbnails_container_client: ContainerClient
    ) -> None:
        filename = "video.mp4"
        with app.app_context():
            videos.delete_thumbnail(filename)

        as_mock(fake_thumbnails_container_client.delete_blob).assert_called_once_with(
            f"{filename}.webp"
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

        filename = "video.mp4"
        with app.app_context():
            videos.delete_thumbnail(filename)

        fake_thumbnails_container_client_delete_blob_mock.assert_called_once_with(
            f"{filename}.webp"
        )
