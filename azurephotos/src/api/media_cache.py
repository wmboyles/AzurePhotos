from datetime import timedelta
from time import monotonic

from ..lib.models.media import MediaRecord

MEDIA_CACHE_TTL = timedelta(minutes=5)
_cached_at = 0.0
media_cache: list[MediaRecord] | None = None
"""
All existing photos and videos not in an album, sorted by last modified time
"""

def all_media() -> list[MediaRecord]:
    from .albums import non_album_file_names
    global media_cache, _cached_at

    if media_cache is not None and timedelta(seconds=monotonic() - _cached_at) < MEDIA_CACHE_TTL:
        return media_cache

    media_cache = sorted(non_album_file_names(), reverse=True)
    _cached_at = monotonic()
    return media_cache

def invalidate_media_cache() -> None:
    global media_cache, _cached_at
    media_cache = None
    _cached_at = 0.0
