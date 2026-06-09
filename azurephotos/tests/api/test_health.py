from urllib import response

import pytest

from azure.core.exceptions import ClientAuthenticationError
from azure.data.tables import TableClient
from azure.storage.blob import ContainerClient
from flask import Flask

from src.api import health
from tests.mocks import as_mock


def test_health_success(
    app: Flask,
    fake_photos_container_client: ContainerClient,
    fake_videos_container_client: ContainerClient,
    fake_thumbnails_container_client: ContainerClient,
    fake_albums_table_client: TableClient,
) -> None:
    with app.app_context():
        response = health.health()

    assert response.status_code == 200
    assert response.content_type == "text/plain"
    assert response.get_data(as_text=True) == "ok"

    as_mock(
        fake_photos_container_client.get_container_properties
    ).assert_called_once_with(timeout=5)
    as_mock(
        fake_videos_container_client.get_container_properties
    ).assert_called_once_with(timeout=5)
    as_mock(
        fake_thumbnails_container_client.get_container_properties
    ).assert_called_once_with(timeout=5)
    as_mock(fake_albums_table_client.list_entities).assert_called_once_with(
        results_per_page=1
    )


def test_health_container_failure(
    app: Flask, fake_photos_container_client: ContainerClient
) -> None:

    error_message = "Unauthorized"
    fake_photos_container_client_get_container_properties_mock = as_mock(
        fake_photos_container_client.get_container_properties
    )
    fake_photos_container_client_get_container_properties_mock.side_effect = (
        ClientAuthenticationError(message=error_message)
    )

    with app.app_context():
        response = health.health()

    fake_photos_container_client_get_container_properties_mock.assert_called_once_with(
        timeout=5
    )

    assert response.status_code == 503
    assert response.content_type == "text/plain"
    assert response.get_data(as_text=True) == error_message


def test_health_table_failure(
    app: Flask, fake_albums_table_client: TableClient
) -> None:

    error_message = "Unauthorized"
    fake_albums_table_client_list_entities_mock = as_mock(
        fake_albums_table_client.list_entities
    )
    fake_albums_table_client_list_entities_mock.side_effect = ClientAuthenticationError(
        message=error_message
    )

    with app.app_context():
        response = health.health()

    fake_albums_table_client_list_entities_mock.assert_called_once_with(
        results_per_page=1
    )

    assert response.status_code == 503
    assert response.content_type == "text/plain"
    assert response.get_data(as_text=True) == error_message
