from azure.identity import DefaultAzureCredential
from flask import current_app
from typing import Sequence

from ..lib.models.media import MediaRecord

# All existing photos and videos not in an album, sorted by last modified time
media_cache: Sequence[MediaRecord] | None = None

def all_media() -> Sequence[MediaRecord]:
    from .albums import non_album_file_names
    global media_cache

    if media_cache is not None:
        return media_cache
    
    account_name: str = current_app.config["account_name"]
    table_name: str = current_app.config["albums_table_name"]
    credential: DefaultAzureCredential = current_app.config["credential"]

    media_cache = sorted(
        non_album_file_names(account_name, table_name, credential),
        reverse=True)
    return media_cache

def invalidate_media_cache() -> None:
    global media_cache
    media_cache = None
