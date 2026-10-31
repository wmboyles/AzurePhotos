from typing import Any

import pytest

from azure.core.exceptions import ResourceExistsError, ResourceNotFoundError
from azure.data.tables import TableClient
from datetime import date, datetime, timezone
from flask import Flask, Response, url_for
from unittest.mock import ANY, call

from tests.mocks import as_mock
from src.api import albums
from src.api.albums import DEFAULT_ALBUM_THUMBNAIL, NONE_ALBUM_NAME, MediaRecord, delete_album
from src.lib.models.media import MediaType


class TestCreateAlbum:
    @pytest.fixture(autouse=True)
    def _setup(
        self,
        app: Flask,
        fake_albums_table_client: TableClient,
    ) -> None:
        self.app = app
        self.table_client = fake_albums_table_client

    def test_create_album_none(self) -> None:
        album_name = NONE_ALBUM_NAME
        with self.app.app_context():
            response = albums.create_album(album_name)

        assert isinstance(response, Response)
        assert response.status_code == 403

        response_text = response.get_data(as_text=True)
        assert response_text == f"{album_name=} is reserved"

    @pytest.mark.parametrize(
        "album_name", ["", "a" * 1025, "/", "\\", "#", "?", "\x1f", "\x7f", "\x9f"]
    )
    def test_create_album_invalid_name(self, album_name: str) -> None:
        album_name = ""
        with self.app.app_context():
            response = albums.create_album(album_name)

        assert isinstance(response, Response)
        assert response.status_code == 422

        response_text = response.get_data(as_text=True)
        assert (
            response_text
            == f"{album_name=} is not allowed due to length or charset restrictions"
        )

    def test_create_album(self) -> None:
        album_name = "Album1"
        with self.app.app_context():
            response = albums.create_album(album_name)

        new_album = {
            "PartitionKey": album_name,
            "RowKey": "",
            "Created": ANY,
        }
        table_client_create_entity_mock = as_mock(self.table_client.create_entity)
        table_client_create_entity_mock.assert_called_once_with(new_album)
        assert table_client_create_entity_mock.return_value == response

    def test_create_album_exists(self) -> None:
        album_name = "Album1"
        table_client_create_entity_mock = as_mock(self.table_client.create_entity)
        table_client_create_entity_mock.side_effect = ResourceExistsError()
        with self.app.app_context():
            response = albums.create_album(album_name)

        assert isinstance(response, Response)
        assert response.status_code == 409

        response_text = response.get_data(as_text=True)
        assert response_text == f"{album_name=} already exists"


class TestListAlbums:
    @pytest.fixture(autouse=True)
    def _setup(
        self,
        app: Flask,
        fake_albums_table_client: TableClient,
    ) -> None:
        self.app = app
        self.table_client = fake_albums_table_client

    @pytest.mark.parametrize(
        "albums_returned",
        ([], [NONE_ALBUM_NAME], ["Album1"], ["Album1", "Album2", "Album3"]),
    )
    def test_list_albums(self, albums_returned: list[str]) -> None:
        table_client_query_entities_mock = as_mock(self.table_client.query_entities)
        table_client_query_entities_mock_return_value = [
            {"RowKey": "", "PartitionKey": album} for album in albums_returned
        ]
        table_client_query_entities_mock.return_value = (
            table_client_query_entities_mock_return_value
        )
        with self.app.test_request_context():
            result = albums.list_albums()

        table_client_query_entities_mock.assert_called_once_with(
            query_filter="PartitionKey ne @reserved_album_name and RowKey eq ''",
            parameters={"reserved_album_name": NONE_ALBUM_NAME},
        )
        assert result == [
            row["PartitionKey"] for row in table_client_query_entities_mock_return_value
        ]


class TestRenameAlbum:
    @pytest.fixture(autouse=True)
    def _setup(
        self,
        app: Flask,
        fake_albums_table_client: TableClient,
    ) -> None:
        self.app = app
        self.table_client = fake_albums_table_client

    def test_rename_album_current_reserved(self) -> None:
        album_name = NONE_ALBUM_NAME
        new_name = "New Album Name"
        with self.app.app_context():
            response = albums.rename_album(album_name, new_name)

        assert response.status_code == 403

        response_text = response.get_data(as_text=True)
        assert response_text == f"{album_name=} is reserved and cannot be renamed"

    def test_rename_album_new_reserved(self) -> None:
        album_name = "Old Album Name"
        new_name = NONE_ALBUM_NAME
        with self.app.app_context():
            response = albums.rename_album(album_name, new_name)

        assert response.status_code == 403

        response_text = response.get_data(as_text=True)
        assert response_text == f"{new_name=} is reserved and cannot be renamed to"

    @pytest.mark.parametrize(
        "new_name", ["", "a" * 1025, "/", "\\", "#", "?", "\x1f", "\x7f", "\x9f"]
    )
    def test_rename_album_new_invalid(self, new_name: str) -> None:
        album_name = "Old Album Name"
        with self.app.app_context():
            response = albums.rename_album(album_name, new_name)

        assert response.status_code == 422

        response_text = response.get_data(as_text=True)
        new_name = new_name.strip()
        assert (
            response_text
            == f"{new_name=} is not allowed due to length or charset restrictions"
        )

    def test_rename_album(self) -> None:
        album_name = "Old Album Name"
        new_name = "New Album Name"
        created = datetime.now(timezone.utc).isoformat()
        query_results = [
            {"PartitionKey": album_name, "RowKey": f"photo_{i}.jpg", "Created": created}
            for i in range(4)
        ]
        query_results_mock = as_mock(self.table_client.query_entities)
        query_results_mock.return_value = query_results

        with self.app.app_context():
            response = albums.rename_album(album_name, new_name)

        assert response.status_code == 204

        query_results_mock.assert_called_once_with(
            query_filter="PartitionKey eq @album_name",
            parameters={"album_name": album_name},
        )

        create_entity_mock = as_mock(self.table_client.create_entity)
        create_entity_mock.assert_has_calls(
            [
                call(
                    {
                        "PartitionKey": new_name,
                        "RowKey": result["RowKey"],
                        "Created": result["Created"],
                    }
                )
                for result in query_results
            ]
        )

        delete_entity_mock = as_mock(self.table_client.delete_entity)
        delete_entity_mock.assert_has_calls(
            [call(result["PartitionKey"], result["RowKey"]) for result in query_results]
        )

    def test_rename_album_missing_old(self) -> None:
        album_name = "Old Album Name"
        new_name = "New Album Name"
        created = datetime.now(timezone.utc).isoformat()
        query_results = [
            {"PartitionKey": album_name, "RowKey": f"photo_{i}.jpg", "Created": created}
            for i in range(4)
        ]
        query_results_mock = as_mock(self.table_client.query_entities)
        query_results_mock.return_value = query_results

        delete_entity_mock = as_mock(self.table_client.delete_entity)
        delete_entity_mock.side_effect = ResourceNotFoundError()

        with self.app.app_context():
            response = albums.rename_album(album_name, new_name)

        assert response.status_code == 204

        query_results_mock.assert_called_once_with(
            query_filter="PartitionKey eq @album_name",
            parameters={"album_name": album_name},
        )

        create_entity_mock = as_mock(self.table_client.create_entity)
        create_entity_mock.assert_has_calls(
            [
                call(
                    {
                        "PartitionKey": new_name,
                        "RowKey": result["RowKey"],
                        "Created": result["Created"],
                    }
                )
                for result in query_results
            ]
        )

        delete_entity_mock.assert_has_calls(
            [call(result["PartitionKey"], result["RowKey"]) for result in query_results]
        )

    def test_rename_album_no_results(self) -> None:
        album_name = "Old Album Name"
        new_name = "New Album Name"
        query_results = []
        query_results_mock = as_mock(self.table_client.query_entities)
        query_results_mock.return_value = query_results

        with self.app.app_context():
            response = albums.rename_album(album_name, new_name)

        assert response.status_code == 404

        response_text = response.get_data(as_text=True)
        assert response_text == f"{album_name=} not found"

        query_results_mock.assert_called_once_with(
            query_filter="PartitionKey eq @album_name",
            parameters={"album_name": album_name},
        )


class TestDeleteAlbum:
    @pytest.fixture(autouse=True)
    def _setup(
        self,
        app: Flask,
        fake_albums_table_client: TableClient,
    ) -> None:
        self.app = app
        self.table_client = fake_albums_table_client

    def test_delete_album_reserved(self) -> None:
        album_name = NONE_ALBUM_NAME
        with self.app.app_context():
            response = albums.delete_album(album_name)

        assert response.status_code == 403

        response_text = response.get_data(as_text=True)
        assert response_text == f"{album_name=} is reserved and cannot be deleted"

    @pytest.mark.parametrize(
        "album_name", ["", "a" * 1025, "/", "\\", "#", "?", "\x1f", "\x7f", "\x9f"]
    )
    def test_delete_album_invalid_name(self, album_name: str) -> None:
        with self.app.app_context():
            response = albums.delete_album(album_name)

        assert response.status_code == 422

        response_text = response.get_data(as_text=True)
        album_name = album_name.strip()
        assert (
            response_text
            == f"{album_name=} is not allowed due to length or charset restrictions"
        )

    def test_delete_album(self) -> None:
        album_name = "Old Album Name"
        created = datetime.now(timezone.utc).isoformat()
        query_results = [
            {"PartitionKey": album_name, "RowKey": f"photo_{i}.jpg", "Created": created}
            for i in range(4)
        ] + [
            {"PartitionKey": album_name, "RowKey": "", "Created": created}
        ]
        query_results_mock = as_mock(self.table_client.query_entities)
        query_results_mock.return_value = query_results

        with self.app.app_context():
            response = albums.delete_album(album_name)

        assert response.status_code == 204

        query_results_mock.assert_called_once_with(
            query_filter="PartitionKey eq @album_name",
            parameters={"album_name": album_name},
        )

        create_entity_mock = as_mock(self.table_client.create_entity)
        create_entity_mock.assert_has_calls([
            call({
                "PartitionKey": NONE_ALBUM_NAME,
                "RowKey": result["RowKey"],
                "Created": result["Created"],
            })
            for result in query_results
            if result["RowKey"]
        ])

        delete_entity_mock = as_mock(self.table_client.delete_entity)
        delete_entity_mock.assert_has_calls([
            call(result["PartitionKey"], result["RowKey"]) for result in query_results
        ])

    def test_delete_album_missing_old(self) -> None:
        album_name = "Old Album Name"
        created = datetime.now(timezone.utc).isoformat()
        query_results = [
            {"PartitionKey": album_name, "RowKey": f"photo_{i}.jpg", "Created": created}
            for i in range(4)
        ]
        query_results_mock = as_mock(self.table_client.query_entities)
        query_results_mock.return_value = query_results

        delete_entity_mock = as_mock(self.table_client.delete_entity)
        delete_entity_mock.side_effect = ResourceNotFoundError()

        with self.app.app_context():
            response = albums.delete_album(album_name)

        assert response.status_code == 204

        query_results_mock.assert_called_once_with(
            query_filter="PartitionKey eq @album_name",
            parameters={"album_name": album_name},
        )

        create_entity_mock = as_mock(self.table_client.create_entity)
        create_entity_mock.assert_has_calls(
            [
                call(
                    {
                        "PartitionKey": NONE_ALBUM_NAME,
                        "RowKey": result["RowKey"],
                        "Created": result["Created"],
                    }
                )
                for result in query_results
            ]
        )

        delete_entity_mock.assert_has_calls(
            [call(result["PartitionKey"], result["RowKey"]) for result in query_results]
        )

    def test_delete_album_no_results(self) -> None:
        album_name = "Old Album Name"
        query_results = []
        query_results_mock = as_mock(self.table_client.query_entities)
        query_results_mock.return_value = query_results

        with self.app.app_context():
            response = albums.delete_album(album_name)

        assert response.status_code == 404

        response_text = response.get_data(as_text=True)
        assert response_text == f"{album_name=} not found"

        query_results_mock.assert_called_once_with(
            query_filter="PartitionKey eq @album_name",
            parameters={"album_name": album_name},
        )


class TestMoveToAlbum:
    @pytest.fixture(autouse=True)
    def _setup(
        self,
        app: Flask,
        fake_albums_table_client: TableClient,
    ) -> None:
        self.app = app
        self.table_client = fake_albums_table_client

    def test_move_to_album_reserved(self) -> None:
        album_name = NONE_ALBUM_NAME
        filename = "photo.jpg"
        with self.app.app_context():
            response = albums.move_to_album(album_name, filename)

        assert response.status_code == 403

        response_text = response.get_data(as_text=True)
        assert (
            response_text
            == f"{album_name=} is reserved and cannot be added to directly"
        )

    @pytest.mark.parametrize(
        "album_name", ["", "a" * 1025, "/", "\\", "#", "?", "\x1f", "\x7f", "\x9f"]
    )
    def test_move_to_album_invalid(self, album_name: str) -> None:
        filename = "photo.jpg"
        with self.app.app_context():
            response = albums.move_to_album(album_name, filename)

        assert response.status_code == 422

        response_text = response.get_data(as_text=True)
        album_name = album_name.strip()
        assert (
            response_text
            == f"{album_name=} is not allowed due to length or charset restrictions"
        )

    def test_move_to_album_noop(self) -> None:
        filename = "photo.jpg"
        album_name = "Album1"
        with self.app.test_request_context(query_string={"currentAlbum": album_name}):
            response = albums.move_to_album(album_name, filename)

        assert response.status_code == 204

    @pytest.mark.parametrize(
        "current_album", ["", "a" * 1025, "/", "\\", "#", "?", "\x1f", "\x7f", "\x9f"]
    )
    def test_move_to_album_current_invalid(self, current_album: str) -> None:
        filename = "photo.jpg"
        album_name = "Album1"
        with self.app.test_request_context(query_string={"currentAlbum": current_album}):
            response = albums.move_to_album(album_name, filename)

        assert response.status_code == 422

        response_text = response.get_data(as_text=True)
        current_album = current_album.strip()
        assert response_text == f"{current_album=} is not allowed due to length or charset restrictions"

    def test_move_to_album_target_not_found(self) -> None:
        filename = "missing.jpg"
        current_album = "Album1"
        target_album_name = "Album2"
        get_entity_mock = as_mock(self.table_client.get_entity)
        get_entity_mock.side_effect = ResourceNotFoundError()

        with self.app.test_request_context(query_string={"currentAlbum": current_album}):
            response = albums.move_to_album(target_album_name, filename)

        assert response.status_code == 404
        get_entity_mock.assert_called_once_with(partition_key=current_album, row_key=filename)

        response_text = response.get_data(as_text=True)
        assert response_text == f"{filename=} does not exist or is not in {current_album=}"

    def test_move_to_album_missing_album(self) -> None:
        filename = "photo.jpg"
        current_album = "Album1"
        album_name = "Album2"
        
        def get_entity_side_effect(*, partition_key: str, row_key: str) -> dict[str, Any]:
            if partition_key == current_album and row_key == filename:
                return {
                    "PartitionKey": partition_key,
                    "RowKey": filename,
                    "Created": datetime.now(timezone.utc).isoformat()
                }

            if partition_key == album_name and row_key == "":
                raise ResourceNotFoundError()

            raise NotImplementedError()
        get_entity_mock = as_mock(self.table_client.get_entity)
        get_entity_mock.side_effect = get_entity_side_effect

        with self.app.test_request_context(query_string={"currentAlbum": current_album}):
            response = albums.move_to_album(album_name, filename)

        assert response.status_code == 404
        assert get_entity_mock.call_count == 2
        assert get_entity_mock.call_args_list == [
            call(partition_key=current_album, row_key=filename),
            call(partition_key=album_name, row_key=""),
        ]

        response_text = response.get_data(as_text=True)
        assert response_text == f"{album_name=} does not exist"

    def test_move_to_album_already_exists(self) -> None:
        filename = "photo.jpg"
        current_album = "Album1"
        album_name = "Album2"
        created = datetime.now(timezone.utc).isoformat()
        
        def get_entity_side_effect(*, partition_key: str, row_key: str) -> dict[str, Any]:
            return {
                "PartitionKey": partition_key,
                "RowKey": filename,
                "Created": created
            }
        get_entity_mock = as_mock(self.table_client.get_entity)
        get_entity_mock.side_effect = get_entity_side_effect

        entity = {
            "PartitionKey": album_name,
            "RowKey": filename,
            "Created": created
        }
        create_entity_mock = as_mock(self.table_client.create_entity)
        create_entity_mock.side_effect = ResourceExistsError()

        delete_entity_mock = as_mock(self.table_client.delete_entity)

        with self.app.test_request_context(query_string={"currentAlbum": current_album}):
            response = albums.move_to_album(album_name, filename)

        assert response.status_code == 201
        assert get_entity_mock.call_count == 2
        assert get_entity_mock.call_args_list == [
            call(partition_key=current_album, row_key=filename),
            call(partition_key=album_name, row_key=""),
        ]

        create_entity_mock.assert_called_once_with(entity=entity)
        delete_entity_mock.assert_called_once_with(partition_key=current_album, row_key=filename)

    def test_move_to_album_already_deleted(self) -> None:
        filename = "photo.jpg"
        current_album = "Album1"
        album_name = "Album2"
        created = datetime.now(timezone.utc).isoformat()
        
        def get_entity_side_effect(*, partition_key: str, row_key: str) -> dict[str, Any]:
            return {
                "PartitionKey": partition_key,
                "RowKey": filename,
                "Created": created
            }
        get_entity_mock = as_mock(self.table_client.get_entity)
        get_entity_mock.side_effect = get_entity_side_effect

        entity = {
            "PartitionKey": album_name,
            "RowKey": filename,
            "Created": created
        }
        create_entity_mock = as_mock(self.table_client.create_entity)
        create_entity_mock.return_value = entity

        delete_entity_mock = as_mock(self.table_client.delete_entity)
        delete_entity_mock.side_effect = ResourceNotFoundError()

        with self.app.test_request_context(query_string={"currentAlbum": current_album}):
            response = albums.move_to_album(album_name, filename)

        assert response.status_code == 201
        assert get_entity_mock.call_count == 2
        assert get_entity_mock.call_args_list == [
            call(partition_key=current_album, row_key=filename),
            call(partition_key=album_name, row_key=""),
        ]

        create_entity_mock.assert_called_once_with(entity=entity)
        delete_entity_mock.assert_called_once_with(partition_key=current_album, row_key=filename)

    @pytest.mark.parametrize(
        "current_album", ["Album1", NONE_ALBUM_NAME]
    )
    def test_move_to_album_success(self, current_album: str) -> None:
        filename = "photo.jpg"
        album_name = "Album2"
        created = datetime.now(timezone.utc).isoformat()
        
        def get_entity_side_effect(*, partition_key: str, row_key: str) -> dict[str, Any]:
            return {
                "PartitionKey": partition_key,
                "RowKey": filename,
                "Created": created
            }
        get_entity_mock = as_mock(self.table_client.get_entity)
        get_entity_mock.side_effect = get_entity_side_effect

        entity = {
            "PartitionKey": album_name,
            "RowKey": filename,
            "Created": created
        }
        create_entity_mock = as_mock(self.table_client.create_entity)
        create_entity_mock.return_value = entity

        delete_entity_mock = as_mock(self.table_client.delete_entity)

        with self.app.test_request_context(query_string={"currentAlbum": current_album}):
            response = albums.move_to_album(album_name, filename)

        assert response.status_code == 201
        assert get_entity_mock.call_count == 2
        assert get_entity_mock.call_args_list == [
            call(partition_key=current_album, row_key=filename),
            call(partition_key=album_name, row_key=""),
        ]

        create_entity_mock.assert_called_once_with(entity=entity)
        delete_entity_mock.assert_called_once_with(partition_key=current_album, row_key=filename)


class TestUploadToAlbum:
    @pytest.fixture(autouse=True)
    def _setup(
        self,
        app: Flask,
        fake_albums_table_client: TableClient,
    ) -> None:
        self.app = app
        self.table_client = fake_albums_table_client

    def test_upload_to_album_not_exists(self) -> None:
        filename = "photo.jpg"
        date_taken = datetime.now(timezone.utc)
        album_name = "Album1"
        get_entity_mock = as_mock(self.table_client.get_entity)
        get_entity_mock.side_effect = ResourceNotFoundError()

        with self.app.test_request_context():
            response = albums.upload_to_album(filename, date_taken, album_name)

        assert response.status_code == 404
        response_text = response.get_data(as_text=True)
        assert response_text == f"{album_name=} does not exist"


class TestListAlbum:
    @pytest.fixture(autouse=True)
    def _setup(
        self,
        app: Flask,
        fake_albums_table_client: TableClient,
    ) -> None:
        self.app = app
        self.table_client = fake_albums_table_client

    def test_list_album_reserved(self) -> None:
        album_name = NONE_ALBUM_NAME
        with self.app.test_request_context():
            response = albums.list_album(album_name)

        assert isinstance(response, Response)
        assert response.status_code == 403
        response_text = response.get_data(as_text=True)
        assert response_text == f"{album_name=} is reserved"

    def test_list_album_invalid(self) -> None:
        album_name = ""
        with self.app.test_request_context():
            response = albums.list_album(album_name)

        assert isinstance(response, Response)

        assert response.status_code == 422
        response_text = response.get_data(as_text=True)
        assert response_text == f"{album_name=} is not allowed due to length or charset restrictions"

    def test_list_album_no_album(self) -> None:
        album_name = "Album1"
        created = datetime.now(timezone.utc)
        query_entites_mock = as_mock(self.table_client.query_entities)

        query_entites_mock.return_value = []

        with self.app.test_request_context():
            response = albums.list_album(album_name)

        assert isinstance(response, Response)
        assert response.status_code == 404
        response_text = response.get_data(as_text=True)
        assert response_text == f"{album_name=} does not exist"

    def test_list_album_success(self) -> None:
        album_name = "Album1"
        created = datetime.now(timezone.utc)
        query_entites_mock = as_mock(self.table_client.query_entities)

        valid_entity1 = MediaRecord(created, "video.mp4", MediaType.VIDEO)
        valid_entity2 = MediaRecord(created, "photo.jpg", MediaType.PHOTO)
        query_entites_mock.return_value = [
            {"PartitionKey": album_name, "RowKey": "", "Created": created},
            {"PartitionKey": album_name, "RowKey": valid_entity1.filename, "Created": valid_entity1.last_modified},
            {"PartitionKey": album_name, "RowKey": f"", "Created": created},
            {"PartitionKey": album_name, "RowKey": f"photo.unknownextension", "Created": created},
            {"PartitionKey": album_name, "RowKey": valid_entity2.filename, "Created": valid_entity2.last_modified},
        ]

        with self.app.test_request_context():
            result = albums.list_album(album_name)

        assert isinstance(result, list)
        assert len(result) == 2
        assert result[0] == valid_entity1
        assert result[1] == valid_entity2


class TestRemoveFromAlbum:
    @pytest.fixture(autouse=True)
    def _setup(
        self,
        app: Flask,
        fake_albums_table_client: TableClient,
    ) -> None:
        self.app = app
        self.table_client = fake_albums_table_client
    
    def test_remove_from_album_reserved(self) -> None:
        album_name = NONE_ALBUM_NAME
        filename = "photo.jpg"

        with self.app.test_request_context():
            response = albums.remove_from_album(album_name, filename)

        assert response.status_code == 403
        response_text = response.get_data(as_text=True)
        assert response_text == f"{album_name=} is reserved and cannot be deleted from"

    def test_remove_from_album_invalid(self) -> None:
        album_name = ""
        filename = "photo.jpg"

        with self.app.test_request_context():
            response = albums.remove_from_album(album_name, filename)

        assert response.status_code == 422
        response_text = response.get_data(as_text=True)
        assert response_text == f"{album_name=} is not allowed due to length or charset restrictions"

    def test_remove_from_album_missing(self) -> None:
        album_name = "Album1"
        filename = "missing.jpg"

        get_entity_mock = as_mock(self.table_client.get_entity)
        get_entity_mock.side_effect = ResourceNotFoundError()

        with self.app.test_request_context():
            response = albums.remove_from_album(album_name, filename)

        assert response.status_code == 404
        response_text = response.get_data(as_text=True)
        assert response_text == f"{filename=} not found in {album_name=}"

    def test_remove_from_album_already_deleted(self) -> None:
        album_name = "Album1"
        filename = "photo.jpg"
        created = datetime.now(timezone.utc)

        get_entity_mock = as_mock(self.table_client.get_entity)
        get_entity_mock.return_value = {"PartitionKey": album_name, "RowKey": filename, "Created": created}

        delete_entity_mock = as_mock(self.table_client.delete_entity)
        delete_entity_mock.side_effect = ResourceNotFoundError()

        with self.app.test_request_context():
            response = albums.remove_from_album(album_name, filename)

        assert response.status_code == 204
        get_entity_mock.assert_called_once_with(partition_key=album_name, row_key=filename)
        delete_entity_mock.assert_called_once_with(partition_key=album_name, row_key=filename)

    def test_remove_from_album_success(self) -> None:
        album_name = "Album1"
        filename = "photo.jpg"
        created = datetime.now(timezone.utc)

        get_entity_mock = as_mock(self.table_client.get_entity)
        get_entity_mock.return_value = {"PartitionKey": album_name, "RowKey": filename, "Created": created}

        delete_entity_mock = as_mock(self.table_client.delete_entity)

        with self.app.test_request_context():
            response = albums.remove_from_album(album_name, filename)

        assert response.status_code == 204
        get_entity_mock.assert_called_once_with(partition_key=album_name, row_key=filename)
        delete_entity_mock.assert_called_once_with(partition_key=album_name, row_key=filename)


class TestGetAlbumThumbnail:
    @pytest.fixture(autouse=True)
    def _setup(
        self,
        app: Flask,
        fake_albums_table_client: TableClient,
    ) -> None:
        self.app = app
        self.table_client = fake_albums_table_client

    def test_get_album_thumbnail_reserved(self) -> None:
        album_name = NONE_ALBUM_NAME

        with self.app.test_request_context():
            response = albums.get_album_thumbnail(album_name)

        assert response.status_code == 403

        response_text = response.get_data(as_text=True)
        assert response_text == f"{album_name=} is reserved"

    def test_get_album_thumbnail_invalid(self) -> None:
        album_name = ""

        with self.app.test_request_context():
            response = albums.get_album_thumbnail(album_name)

        assert response.status_code == 422

        response_text = response.get_data(as_text=True)
        assert response_text == f"{album_name=} is not allowed due to length or charset restrictions"

    def test_get_album_thumbnail_empty(self) -> None:
        album_name = "Album1"

        query_entities_mock = as_mock(self.table_client.query_entities)
        query_entities_mock.return_value = iter(list())

        with self.app.test_request_context():
            response = albums.get_album_thumbnail(album_name)

        query_entities_mock.assert_called_once()

        assert response.status_code == 302
        assert response.headers["Location"] == DEFAULT_ALBUM_THUMBNAIL

    def test_get_album_thumbnail_success(self) -> None:
        album_name = "Album1"
        created = datetime.now(timezone.utc)

        query_entities_mock = as_mock(self.table_client.query_entities)
        query_entities_mock.return_value = (
            {"PartitionKey": album_name, "RowKey": f"photo_{i}.jpg", "Created": created}
            for i in range(4)
        )

        with self.app.test_request_context():
            response = albums.get_album_thumbnail(album_name)
            expected_location = url_for("crud_controller.thumbnail", filename="photo_0.jpg")

        query_entities_mock.assert_called_once()

        assert response.status_code == 302
        assert response.headers["Location"] == expected_location


class TestRemoveFromAllAlbums:
    @pytest.fixture(autouse=True)
    def _setup(
        self,
        app: Flask,
        fake_albums_table_client: TableClient,
    ) -> None:
        self.app = app
        self.table_client = fake_albums_table_client

    def test_remove_from_all_albums_already_deleted(self) -> None:
        filename = "photo1.jpg"
        created = datetime.now(timezone.utc)

        query_entity_mock = as_mock(self.table_client.query_entities)
        query_entity_mock.return_value = (
            {"PartitionKey": f"Album{i}", "RowKey": filename, "Created": created}
            for i in range(4)
        )

        def delete_entity_side_effect(entity: dict[str, Any]) -> None:
            if entity["PartitionKey"] == "Album3":
                raise ResourceNotFoundError()
        delete_entity_mock = as_mock(self.table_client.delete_entity)
        delete_entity_mock.side_effect = delete_entity_side_effect

        with self.app.test_request_context():
            albums_affected = albums.remove_from_all_albums(filename)

        delete_entity_mock.assert_called_with({"PartitionKey": f"Album3", "RowKey": filename, "Created": created})
        assert albums_affected == {"Album0", "Album1", "Album2"}


class TestNonAlbumFileNames:
    def test_non_album_file_names_success(self) -> None:
        ...
