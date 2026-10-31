import pytest

from datetime import datetime, timezone, timedelta
from unittest.mock import Mock

from src.api import media_cache, albums
from src.lib.models.media import MediaRecord, MediaType


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
