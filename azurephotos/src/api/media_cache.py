from azure.identity import DefaultAzureCredential
from flask import current_app
from functools import wraps
from typing import Sequence

from ..lib.models.media import MediaRecord

# All existing photos and videos not in an album, sorted by last modified time
media_cache: Sequence[MediaRecord] | None = None

def all_media() -> Sequence[MediaRecord]:
    from .albums import non_album_file_names
    global media_cache

    if media_cache is not None:
        print("SERVED MEDIA FROM CACHE")
        return media_cache
    
    print("RECALCULATING MEDIA")
    
    account_name: str = current_app.config["account_name"]
    table_name: str = current_app.config["albums_table_name"]
    credential: DefaultAzureCredential = current_app.config["credential"]

    # TODO: Fix ordering, which is ruined when using 'Created' in a table
    media_cache = non_album_file_names(account_name, table_name, credential)
    return media_cache

def invalidates_media_cache(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        global media_cache
        result = func(*args, **kwargs)
        media_cache = None
        print("INVALIDATED MEDIA CACHE")
        return result

    return wrapper
