import pytest

from azure.core.exceptions import ResourceExistsError, ResourceNotFoundError
from azure.data.tables import TableClient
from datetime import datetime, timezone
from flask import Flask, Response
from unittest.mock import ANY, call

from tests.mocks import as_mock
from src.api import albums
from src.api.albums import NONE_ALBUM_NAME, delete_album


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
        "album_name", ["", "a" * 1025, "/", "\\", "#", "?", "\x1F", "\x7F", "\x9F"]
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


@pytest.mark.parametrize(
    "albums_returned",
    ([], [NONE_ALBUM_NAME], ["Album1"], ["Album1", "Album2", "Album3"]),
)
def test_list_albums(
    app: Flask, fake_albums_table_client: TableClient, albums_returned: list[str]
) -> None:
    table_client_query_entities_mock = as_mock(fake_albums_table_client.query_entities)
    table_client_query_entities_mock_return_value = [
        {"RowKey": "", "PartitionKey": album} for album in albums_returned
    ]
    table_client_query_entities_mock.return_value = (
        table_client_query_entities_mock_return_value
    )
    with app.app_context():
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
        "new_name", ["", "a" * 1025, "/", "\\", "#", "?", "\x1F", "\x7F", "\x9F"]
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
        "album_name", ["", "a" * 1025, "/", "\\", "#", "?", "\x1F", "\x7F", "\x9F"]
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

        delete_entity_mock = as_mock(self.table_client.delete_entity)
        delete_entity_mock.assert_has_calls(
            [call(result["PartitionKey"], result["RowKey"]) for result in query_results]
        )

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
