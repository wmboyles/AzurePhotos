import pytest

from azure.data.tables import TableClient
from datetime import datetime, timezone, timedelta
from flask import Flask
from unittest.mock import Mock

from src.api import media_cache, albums
from src.lib.models.media import MediaRecord, MediaType
from tests.mocks import as_mock


@pytest.fixture(autouse=True)
def reset_media_cache():
    media_cache.invalidate_media_cache()
    yield
    media_cache.invalidate_media_cache()


def test_invalidate_media_cache() -> None:
    media_cache.media_cache = []  # Something other than None
    media_cache.invalidate_media_cache()
    assert media_cache.media_cache is None


def test_all_media(monkeypatch: pytest.MonkeyPatch) -> None:
    dt = datetime(2026, 1, 1, tzinfo=timezone.utc)
    delta = timedelta(minutes=10)
    mocked_non_album_file_names = [
        MediaRecord.from_filename(dt + delta, "photo2.jpg"),
        MediaRecord.from_filename(dt, "video2.mp4"),
        MediaRecord.from_filename(dt, "video1.mp4"),
        MediaRecord.from_filename(dt - delta, "photo1.jpg"),
    ]
    non_album_file_names_mock = Mock(return_value=mocked_non_album_file_names)
    monkeypatch.setattr(
        albums, "non_album_file_names", lambda: non_album_file_names_mock()
    )

    # Prereq: Media cache is invalidated
    media_cache.invalidate_media_cache()

    # Ordering is by last_modified (youngest first), then filename (latest alphabetically first)
    result = media_cache.all_media()

    assert media_cache.media_cache == result
    assert len(result) == len(mocked_non_album_file_names)
    non_album_file_names_mock.assert_called_once()

    assert result[0].last_modified == dt + delta
    assert result[0].type == MediaType.PHOTO
    assert result[0].filename == "photo2.jpg"

    assert result[1].last_modified == dt
    assert result[1].type == MediaType.VIDEO
    assert result[1].filename == "video2.mp4"

    assert result[2].last_modified == dt
    assert result[2].type == MediaType.VIDEO
    assert result[2].filename == "video1.mp4"

    assert result[3].last_modified == dt - delta
    assert result[3].type == MediaType.PHOTO
    assert result[3].filename == "photo1.jpg"

    # Mock is not called again because we use cached value on subsequent calls
    result2 = media_cache.all_media()

    assert result2 == result
    non_album_file_names_mock.assert_called_once()


@pytest.mark.parametrize("empty_cache", [False, True])
def test_all_media_expires_after_five_minutes(
    monkeypatch: pytest.MonkeyPatch, empty_cache: bool
) -> None:
    dt = datetime(2026, 1, 1, tzinfo=timezone.utc)
    initial = [] if empty_cache else [MediaRecord(dt, "first.jpg", MediaType.PHOTO)]
    updated = [MediaRecord(dt, "new.jpg", MediaType.PHOTO)]
    storage = Mock(side_effect=[initial, updated])
    monkeypatch.setattr(albums, "non_album_file_names", storage)
    now = [100.0]
    monkeypatch.setattr(media_cache, "monotonic", lambda: now[0])
    ttl = timedelta(minutes=5)

    assert media_cache.all_media() == initial
    now[0] = 100.0 + (ttl - timedelta(milliseconds=100)).total_seconds()
    assert media_cache.all_media() == initial
    storage.assert_called_once()
    now[0] = 100.0 + ttl.total_seconds()
    assert media_cache.all_media() == updated
    assert storage.call_count == 2


def test_invalidation_reads_storage_without_waiting_for_expiry(
    app: Flask, fake_albums_table_client: TableClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    dt = datetime(2026, 1, 1, tzinfo=timezone.utc)
    storage = as_mock(fake_albums_table_client.query_entities)
    storage.side_effect = [
        [{"RowKey": "first.jpg", "Created": dt}],
        [{"RowKey": "new.jpg", "Created": dt}],
    ]
    monkeypatch.setattr(media_cache, "monotonic", lambda: 100.0)

    with app.app_context():
        assert media_cache.all_media()[0].filename == "first.jpg"
        media_cache.invalidate_media_cache()
        assert media_cache.all_media()[0].filename == "new.jpg"
    assert storage.call_count == 2


def test_expired_cache_surfaces_storage_failure_and_retries(
    monkeypatch: pytest.MonkeyPatch
) -> None:
    storage = Mock(side_effect=[[], RuntimeError("storage unavailable"), []])
    monkeypatch.setattr(albums, "non_album_file_names", storage)
    now = [100.0]
    monkeypatch.setattr(media_cache, "monotonic", lambda: now[0])

    assert media_cache.all_media() == []
    now[0] += timedelta(minutes=5).total_seconds()
    with pytest.raises(RuntimeError, match="storage unavailable"):
        media_cache.all_media()
    assert media_cache.all_media() == []
    assert storage.call_count == 3
