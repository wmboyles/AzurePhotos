from typing import Sequence

from ..lib.models.media import MediaRecord

media_cache: Sequence[MediaRecord] | None = None
"""
All existing photos and videos not in an album, sorted by last modified time
"""

def all_media() -> Sequence[MediaRecord]:
    from .albums import non_album_file_names
    global media_cache

    if media_cache is not None:
        return media_cache
    

    media_cache = sorted(non_album_file_names(), reverse=True)
    return media_cache

def invalidate_media_cache() -> None:
    global media_cache
    media_cache = None
