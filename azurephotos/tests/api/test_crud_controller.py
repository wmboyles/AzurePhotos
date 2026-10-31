import pytest

from azure.core.exceptions import ResourceExistsError, ResourceNotFoundError
from azure.data.tables import TableClient
from azure.storage.blob import ContainerClient, ContentSettings
from datetime import datetime, timezone
from flask import Flask
from io import BytesIO
from unittest.mock import ANY, call
from werkzeug.wrappers.response import Response
from werkzeug.datastructures.file_storage import FileStorage

from src.api import crud_controller, photos, videos
from src.api.albums import NONE_ALBUM_NAME
from src.lib.models.media import MediaType
from tests.mocks import as_mock


@pytest.mark.parametrize("filename", ("photo.jpg", "video.mp4"))
def test_thumbnail(app: Flask, monkeypatch: pytest.MonkeyPatch, filename: str) -> None:
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

    expected_location = (
        f"{app.config["blob_account_url"]}/photos/{filename}?{photos_container_sas}"
    )
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

    expected_location = (
        f"{app.config["blob_account_url"]}/videos/{filename}?{videos_container_sas}"
    )
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


class TestUpload:
    _THUMBNAIL_BYTES = BytesIO(b"thumbnail-bytes")

    @pytest.fixture(autouse=True)
    def _setup(
        self,
        app: Flask,
        monkeypatch: pytest.MonkeyPatch,
        fake_photos_container_client: ContainerClient,
        fake_videos_container_client: ContainerClient,
        fake_thumbnails_container_client: ContainerClient,
        fake_albums_table_client: TableClient,
    ) -> None:
        self.app = app
        self.photo_client = fake_photos_container_client
        self.video_client = fake_videos_container_client
        self.thumbnails_client = fake_thumbnails_container_client
        self.table_client = fake_albums_table_client

        monkeypatch.setattr(
            photos, "compute_thumbnail", lambda _: TestUpload._THUMBNAIL_BYTES
        )
        monkeypatch.setattr(
            videos, "compute_thumbnail", lambda _, __: TestUpload._THUMBNAIL_BYTES
        )

    @staticmethod
    def make_file(
        filename: str = "photo.jpg", content: bytes = b"photo-data"
    ) -> FileStorage:
        return FileStorage(stream=BytesIO(content), filename=filename)

    @pytest.mark.parametrize("album_name", (NONE_ALBUM_NAME, "Test Album"))
    def test_upload_photo(self, album_name: str) -> None:
        filename = "photo.jpg"
        content = b"photo-bytes"
        file = self.make_file(filename=filename, content=content)
        date_taken = datetime(2026, 1, 1, tzinfo=timezone.utc)

        with self.app.test_request_context(
            method="POST", data={"upload": file, "dateTaken": date_taken}
        ):
            result = (
                crud_controller.upload()
                if album_name == NONE_ALBUM_NAME
                else crud_controller.upload_to_album(album_name)
            )

        assert result.status_code == 201

        expected_metadata = {"lastModified": date_taken.isoformat()}

        upload_fullsize_blob_mock = as_mock(self.photo_client.upload_blob)
        upload_fullsize_blob_mock.assert_called_once_with(
            name=filename,
            data=ANY,  # by reference, so can't compare
            length=len(content),
            max_concurrency=4,
            metadata=expected_metadata,
        )

        upload_thumbnail_blob_mock = as_mock(self.thumbnails_client.upload_blob)
        upload_thumbnail_blob_mock.assert_called_once_with(
            name=filename,
            data=TestUpload._THUMBNAIL_BYTES,
            metadata=expected_metadata,
            content_settings=ContentSettings(
                cache_control="public, max-age=31536000, immutable"
            ),
        )

        upload_album_mock = as_mock(self.table_client.create_entity)
        expected_album_entry = {
            "PartitionKey": album_name,
            "RowKey": filename,
            "Created": date_taken,
        }
        upload_album_mock.assert_called_once_with(expected_album_entry)

    @pytest.mark.parametrize("album_name", (NONE_ALBUM_NAME, "Test Album"))
    def test_upload_video(self, album_name: str) -> None:
        filename = "video.mp4"
        content = b"video-bytes"
        file = self.make_file(filename=filename, content=content)
        date_taken = datetime(2026, 1, 1, tzinfo=timezone.utc)

        with self.app.test_request_context(
            method="POST", data={"upload": file, "dateTaken": date_taken}
        ):
            result = (
                crud_controller.upload()
                if album_name == NONE_ALBUM_NAME
                else crud_controller.upload_to_album(album_name)
            )

        assert result.status_code == 201

        expected_metadata = {"lastModified": date_taken.isoformat()}

        upload_fullsize_blob_mock = as_mock(self.video_client.upload_blob)
        upload_fullsize_blob_mock.assert_called_once_with(
            name=filename,
            data=ANY,  # by reference, so can't compare
            length=len(content),
            max_concurrency=4,
            metadata=expected_metadata,
        )

        upload_thumbnail_blob_mock = as_mock(self.thumbnails_client.upload_blob)
        upload_thumbnail_blob_mock.assert_called_once_with(
            name=f"{filename}.webp",
            data=TestUpload._THUMBNAIL_BYTES,
            metadata=expected_metadata,
            content_settings=ContentSettings(
                cache_control="public, max-age=31536000, immutable"
            ),
        )

        upload_album_mock = as_mock(self.table_client.create_entity)
        expected_album_entry = {
            "PartitionKey": album_name,
            "RowKey": filename,
            "Created": date_taken,
        }
        upload_album_mock.assert_called_once_with(expected_album_entry)

    @pytest.mark.parametrize("album_name", (NONE_ALBUM_NAME, "Test Album"))
    def test_upload_no_files(self, album_name: str) -> None:
        date_taken = datetime(2026, 1, 1, tzinfo=timezone.utc)

        with pytest.raises(
            ValueError, match="No files provided for upload"
        ), self.app.test_request_context(
            method="POST", data={"upload": None, "dateTaken": date_taken}
        ):
            _ = (
                crud_controller.upload()
                if album_name == NONE_ALBUM_NAME
                else crud_controller.upload_to_album(album_name)
            )

    @pytest.mark.parametrize("album_name", (NONE_ALBUM_NAME, "Test Album"))
    def test_upload_no_dates(self, album_name: str) -> None:
        filename = "photo.jpg"
        content = b"photo-bytes"
        file = self.make_file(filename=filename, content=content)

        with pytest.raises(
            ValueError, match="No dates provided for uploaded items"
        ), self.app.test_request_context(
            method="POST", data={"upload": file, "dateTaken": []}
        ):
            _ = (
                crud_controller.upload()
                if album_name == NONE_ALBUM_NAME
                else crud_controller.upload_to_album(album_name)
            )

    @pytest.mark.parametrize("album_name", (NONE_ALBUM_NAME, "Test Album"))
    def test_upload_extra_files(self, album_name: str) -> None:
        content = b"photo-bytes"
        file1 = self.make_file(filename="photo1.jpg", content=content)
        file2 = self.make_file(filename="photo2.jpg", content=content)
        date_taken = datetime(2026, 1, 1, tzinfo=timezone.utc)

        with pytest.raises(
            ValueError,
            match="Number of uploaded files and number of dates do not match",
        ), self.app.test_request_context(
            method="POST", data={"upload": [file1, file2], "dateTaken": date_taken}
        ):
            _ = (
                crud_controller.upload()
                if album_name == NONE_ALBUM_NAME
                else crud_controller.upload_to_album(album_name)
            )

    @pytest.mark.parametrize("album_name", (NONE_ALBUM_NAME, "Test Album"))
    def test_upload_extra_dates(self, album_name: str) -> None:
        content = b"photo-bytes"
        file = self.make_file(filename="photo1.jpg", content=content)
        date_taken1 = datetime(2026, 1, 1, tzinfo=timezone.utc)
        date_taken2 = datetime(2026, 1, 2, tzinfo=timezone.utc)

        with pytest.raises(
            ValueError,
            match="Number of uploaded files and number of dates do not match",
        ), self.app.test_request_context(
            method="POST",
            data={"upload": file, "dateTaken": [date_taken1, date_taken2]},
        ):
            _ = (
                crud_controller.upload()
                if album_name == NONE_ALBUM_NAME
                else crud_controller.upload_to_album(album_name)
            )

    @pytest.mark.parametrize("album_name", (NONE_ALBUM_NAME, "Test Album"))
    def test_upload_unrecognized_extension(self, album_name: str) -> None:
        filename = "unknown_extension.idk"
        content = b"photo-bytes"
        file = self.make_file(filename=filename, content=content)
        date_taken1 = datetime(2026, 1, 1, tzinfo=timezone.utc)

        with pytest.raises(
            ValueError,
            match=f"Unrecognized media type for {file.filename=}",
        ), self.app.test_request_context(
            method="POST", data={"upload": file, "dateTaken": date_taken1}
        ):
            _ = (
                crud_controller.upload()
                if album_name == NONE_ALBUM_NAME
                else crud_controller.upload_to_album(album_name)
            )

    @pytest.mark.parametrize("album_name", (NONE_ALBUM_NAME, "Test Album"))
    def test_upload_no_filename(self, album_name: str) -> None:
        content = b"photo-bytes"
        file = self.make_file(filename="", content=content)
        date_taken = datetime(2026, 1, 1, tzinfo=timezone.utc)

        with pytest.raises(
            ValueError, match="File must have filename"
        ), self.app.test_request_context(
            method="POST", data={"upload": [file], "dateTaken": date_taken}
        ):
            _ = (
                crud_controller.upload()
                if album_name == NONE_ALBUM_NAME
                else crud_controller.upload_to_album(album_name)
            )

    def test_upload_to_album_reserved_album(self) -> None:
        filename = "photo.jpg"
        content = b"photo-bytes"
        file = self.make_file(filename=filename, content=content)
        date_taken = datetime(2026, 1, 1, tzinfo=timezone.utc)

        with self.app.test_request_context(
            method="POST", data={"upload": file, "dateTaken": date_taken}
        ):
            response = crud_controller.upload_to_album(NONE_ALBUM_NAME)

        assert response.status_code == 403
        assert response.content_type == "text/plain; charset=utf-8"
        response_text = response.get_data(as_text=True)
        assert (
            response_text
            == f"Album name '{NONE_ALBUM_NAME}' is reserved and cannot be uploaded to directly"
        )

    @pytest.mark.parametrize(
        "album_name", ["", "a" * 1025, "/", "\\", "#", "?", "\x1F", "\x7F", "\x9F"]
    )
    def test_upload_bad_album_name(self, album_name: str) -> None:
        filename = "photo.jpg"
        content = b"photo-bytes"
        file = self.make_file(filename=filename, content=content)
        date_taken = datetime(2026, 1, 1, tzinfo=timezone.utc)

        with self.app.test_request_context(
            method="POST", data={"upload": file, "dateTaken": date_taken}
        ):
            response = crud_controller.upload_to_album(album_name)

        assert response.status_code == 400
        assert response.content_type == "application/json"
        album_name = album_name.strip()
        assert response.json == [
            {
                "filename": filename,
                "status_code": 422,
                "message": f"{album_name=} is not allowed due to length or charset restrictions",
            }
        ]

    @pytest.mark.parametrize("album_name", (NONE_ALBUM_NAME, "Test Album"))
    def test_upload_resource_exists(
        self, album_name: str, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        filename = "photo.jpg"
        content = b"photo-bytes"
        file = self.make_file(filename=filename, content=content)
        date_taken = datetime(2026, 1, 1, tzinfo=timezone.utc)

        error_message = f"{filename=} already exists"
        as_mock(self.photo_client.upload_blob).side_effect = ResourceExistsError(
            error_message
        )

        with self.app.test_request_context(
            method="POST", data={"upload": file, "dateTaken": date_taken}
        ):
            response = (
                crud_controller.upload()
                if album_name == NONE_ALBUM_NAME
                else crud_controller.upload_to_album(album_name)
            )

        assert response.status_code == 400
        assert response.content_type == "application/json"
        assert response.json == [
            {"filename": filename, "status_code": 409, "message": error_message}
        ]


class TestDelete:
    @pytest.fixture(autouse=True)
    def _setup(
        self,
        app: Flask,
        fake_photos_container_client: ContainerClient,
        fake_videos_container_client: ContainerClient,
        fake_thumbnails_container_client: ContainerClient,
        fake_albums_table_client: TableClient,
    ) -> None:
        self.app = app
        self.photo_client = fake_photos_container_client
        self.video_client = fake_videos_container_client
        self.thumbnails_client = fake_thumbnails_container_client
        self.table_client = fake_albums_table_client

    def test_delete_unknown_extension(self) -> None:
        filename = "unknown_extension.idk"

        with self.app.app_context():
            response = crud_controller.delete(filename)

        assert response.status_code == 415
        response_text = response.get_data(as_text=True)
        assert response_text == f"Unrecognized media type for {filename=}"

    @pytest.mark.parametrize(
        "albums_affected",
        ([NONE_ALBUM_NAME], ["Album1"], ["Album1", "Album2", "Album3"]),
    )
    def test_delete_photo(self, albums_affected: list[str]) -> None:
        filename = "photo.jpg"
        table_client_query_mock = as_mock(self.table_client.query_entities)
        table_client_query_mock_return_value = [
            {"PartitionKey": album, "RowKey": filename} for album in albums_affected
        ]
        table_client_query_mock.return_value = table_client_query_mock_return_value
        with self.app.app_context():
            response = crud_controller.delete(filename)

        assert response.status_code == 204

        photo_client_delete_blob_mock = as_mock(self.photo_client.delete_blob)
        photo_client_delete_blob_mock.assert_called_once_with(filename)

        thumbnails_client_delete_blob_mock = as_mock(self.thumbnails_client.delete_blob)
        thumbnails_client_delete_blob_mock.assert_called_once_with(filename)

        table_client_query_mock.assert_called_once_with(
            query_filter="RowKey eq @filename", parameters={"filename": filename}
        )

        table_client_delete_mock = as_mock(self.table_client.delete_entity)
        table_client_delete_mock.assert_has_calls(
            [call(entity) for entity in table_client_query_mock_return_value]
        )

    def test_delete_photo_missing_fullsize(self) -> None:
        photo_client_delete_blob_mock = as_mock(self.photo_client.delete_blob)
        photo_client_delete_blob_mock.side_effect = ResourceNotFoundError()
        filename = "photo.jpg"
        with self.app.app_context():
            response = crud_controller.delete(filename)

        assert response.status_code == 204

        photo_client_delete_blob_mock.assert_called_once_with(filename)

        thumbnails_client_delete_blob_mock = as_mock(self.thumbnails_client.delete_blob)
        thumbnails_client_delete_blob_mock.assert_called_once_with(filename)

    def test_delete_photo_missing_thumbnail(self) -> None:
        thumbnails_client_delete_blob_mock = as_mock(self.thumbnails_client.delete_blob)
        thumbnails_client_delete_blob_mock.side_effect = ResourceNotFoundError()
        filename = "photo.jpg"
        with self.app.app_context():
            response = crud_controller.delete(filename)

        assert response.status_code == 204

        photo_client_delete_blob_mock = as_mock(self.photo_client.delete_blob)
        photo_client_delete_blob_mock.assert_called_once_with(filename)

        thumbnails_client_delete_blob_mock.assert_called_once_with(filename)

    @pytest.mark.parametrize(
        "albums_affected",
        ([NONE_ALBUM_NAME], ["Album1"], ["Album1", "Album2", "Album3"]),
    )
    def test_delete_video(self, albums_affected: list[str]) -> None:
        filename = "video.mp4"
        table_client_query_mock = as_mock(self.table_client.query_entities)
        table_client_query_mock_return_value = [
            {"PartitionKey": album, "RowKey": filename} for album in albums_affected
        ]
        table_client_query_mock.return_value = table_client_query_mock_return_value
        with self.app.app_context():
            response = crud_controller.delete(filename)

        assert response.status_code == 204

        video_client_delete_blob_mock = as_mock(self.video_client.delete_blob)
        video_client_delete_blob_mock.assert_called_once_with(filename)

        thumbnails_client_delete_blob_mock = as_mock(self.thumbnails_client.delete_blob)
        thumbnails_client_delete_blob_mock.assert_called_once_with(f"{filename}.webp")

        table_client_query_mock.assert_called_once_with(
            query_filter="RowKey eq @filename", parameters={"filename": filename}
        )

        table_client_delete_mock = as_mock(self.table_client.delete_entity)
        table_client_delete_mock.assert_has_calls(
            [call(entity) for entity in table_client_query_mock_return_value]
        )

    def test_delete_video_missing_fullsize(self) -> None:
        video_client_delete_blob_mock = as_mock(self.video_client.delete_blob)
        video_client_delete_blob_mock.side_effect = ResourceNotFoundError()
        filename = "video.mp4"
        with self.app.app_context():
            response = crud_controller.delete(filename)

        assert response.status_code == 204

        video_client_delete_blob_mock.assert_called_once_with(filename)

        thumbnails_client_delete_blob_mock = as_mock(self.thumbnails_client.delete_blob)
        thumbnails_client_delete_blob_mock.assert_called_once_with(f"{filename}.webp")

    def test_delete_video_missing_thumbnail(self) -> None:
        thumbnails_client_delete_blob_mock = as_mock(self.thumbnails_client.delete_blob)
        thumbnails_client_delete_blob_mock.side_effect = ResourceNotFoundError()
        filename = "video.mp4"
        with self.app.app_context():
            response = crud_controller.delete(filename)

        assert response.status_code == 204

        video_client_delete_blob_mock = as_mock(self.video_client.delete_blob)
        video_client_delete_blob_mock.assert_called_once_with(filename)

        thumbnails_client_delete_blob_mock.assert_called_once_with(f"{filename}.webp")
