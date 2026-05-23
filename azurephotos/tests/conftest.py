import pytest
from unittest.mock import MagicMock
from flask import Flask

from src.api.albums import api_albums_controller
from src.api.crud_controller import crud_controller
from src.api.health import api_health_controller


@pytest.fixture
def fake_table_client():
    return MagicMock(name="albums_table_client")


@pytest.fixture
def fake_photos_client():
    return MagicMock(name="photos_container_client")


@pytest.fixture
def fake_thumbnails_client():
    return MagicMock(name="thumbnails_container_client")


@pytest.fixture
def fake_videos_client():
    return MagicMock(name="videos_container_client")


@pytest.fixture
def app(fake_table_client, fake_photos_client, fake_thumbnails_client, fake_videos_client):
    app = Flask(__name__)
    app.config.update(
        account_name="testaccount",
        blob_account_url="https://testaccount.blob.core.windows.net",
        albums_table_client=fake_table_client,
        photos_container_client=fake_photos_client,
        thumbnails_container_client=fake_thumbnails_client,
        videos_container_client=fake_videos_client,
        TESTING=True,
    )
    app.register_blueprint(api_albums_controller)
    app.register_blueprint(crud_controller)
    app.register_blueprint(api_health_controller)
    return app


@pytest.fixture
def client(app):
    return app.test_client()