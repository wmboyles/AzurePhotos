import pytest

from azure.storage.blob import BlobServiceClient
from flask import Flask

from src.lib import storage_helper
from tests.mocks import as_mock

def test_get_container_sas_cached(
    app: Flask,
    fake_blob_service_client: BlobServiceClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        storage_helper,
        "generate_container_sas",
        lambda **kwargs: "token",
    )

    with app.app_context():
        first = storage_helper.get_container_sas("photos")
        second = storage_helper.get_container_sas("photos")

    assert first == second

    assert as_mock(fake_blob_service_client.get_user_delegation_key).call_count == 1
