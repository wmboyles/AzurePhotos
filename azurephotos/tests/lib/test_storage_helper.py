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


def test_sas_content_type_is_signed_and_cached_separately(
    app: Flask, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = []
    def fake_generate(**kwargs) -> str:
        calls.append(kwargs)
        return kwargs["content_type"]
    monkeypatch.setattr(storage_helper, "generate_container_sas", fake_generate)

    with app.app_context():
        assert storage_helper.get_container_sas("videos", content_type="video/mp4") == "video/mp4"
        assert storage_helper.get_container_sas("videos", content_type="video/quicktime") == "video/quicktime"
        assert storage_helper.get_container_sas("videos", content_type="video/mp4") == "video/mp4"

    assert [call["content_type"] for call in calls] == ["video/mp4", "video/quicktime"]
    assert all(call["permission"].read and not call["permission"].write for call in calls)
