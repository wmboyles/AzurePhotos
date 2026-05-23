import pytest

from flask import Flask
from flask.testing import FlaskClient
from unittest.mock import MagicMock

import src.view.view as view
import src.api.api as api

ACCOUNT_NAME = "testaccount"


@pytest.fixture
def fake_blob_service_client() -> MagicMock:
    client = MagicMock(name="blob_service_client")
    client.account_name = ACCOUNT_NAME
    client.get_user_delegation_key.return_value = "fake-key"
    return client


@pytest.fixture
def fake_photos_container_client() -> MagicMock:
    return MagicMock(name="photos_container_client")


@pytest.fixture
def fake_videos_container_client() -> MagicMock:
    return MagicMock(name="videos_container_client")


@pytest.fixture
def fake_thumbnails_container_client() -> MagicMock:
    return MagicMock(name="thumbnails_container_client")


@pytest.fixture
def fake_albums_table_client() -> MagicMock:
    return MagicMock(name="albums_table_client")


@pytest.fixture
def app(
    fake_blob_service_client: MagicMock,
    fake_photos_container_client: MagicMock,
    fake_videos_container_client: MagicMock,
    fake_thumbnails_container_client: MagicMock,
    fake_albums_table_client: MagicMock,
) -> Flask:
    app = Flask(__name__)

    with app.app_context():
        app.config.update(
            blob_account_url=f"https://{ACCOUNT_NAME}.blob.core.windows.net",
            blob_service_client=fake_blob_service_client,
            photos_container_client=fake_photos_container_client,
            videos_container_client=fake_videos_container_client,
            thumbnails_container_client=fake_thumbnails_container_client,
            albums_table_client=fake_albums_table_client,
            SEND_FILE_MAX_AGE_DEFAULT=86400,
            MAX_CONTENT_LENGTH=200 * 1024 * 1024,  # 200 MB
            TESTING=True,
        )
        for blueprint in view.blueprints:
            app.register_blueprint(blueprint)
        for blueprint in api.blueprints:
            app.register_blueprint(blueprint)

    return app


@pytest.fixture
def client(app: Flask) -> FlaskClient:
    return app.test_client()
