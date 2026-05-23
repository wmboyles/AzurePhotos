import pytest

from flask import Flask
from unittest.mock import MagicMock

from src.lib import storage_helper


def test_get_container_sas_cached(
    app: Flask,
    fake_blob_service_client: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(
        storage_helper,
        "generate_container_sas",
        lambda **kwargs: "token",
    )

    with app.app_context():
        first = storage_helper.get_container_sas("photos")
        second = storage_helper.get_container_sas("photos")

    assert first == second

    assert fake_blob_service_client.get_user_delegation_key.call_count == 1
