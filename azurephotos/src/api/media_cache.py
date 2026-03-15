from azure.identity import DefaultAzureCredential
from concurrent.futures import ThreadPoolExecutor
from flask import current_app
from functools import wraps
from typing import Sequence

from ..lib.models.media import MediaRecord

# All existing photos and videos not in an album, sorted by last modified time
media_cache: Sequence[MediaRecord] | None = None

def all_media() -> Sequence[MediaRecord]:
    from .photos import all_photos
    from .videos import all_videos
    from .albums import all_album_file_names
    from ..lib.sorting import merge
    global media_cache

    if media_cache is not None:
        print("SERVED MEDIA FROM CACHE")
        return media_cache
    
    print("RECALCULATING MEDIA")
    
    account_name: str = current_app.config["account_name"]
    photos_container_name: str = current_app.config["photos_container_name"]
    videos_container_name: str = current_app.config["videos_container_name"]
    table_name: str = current_app.config["albums_table_name"]
    credential: DefaultAzureCredential = current_app.config["credential"]

    with ThreadPoolExecutor() as executor:
        photos_future = executor.submit(all_photos, account_name, photos_container_name, credential)
        videos_future = executor.submit(all_videos, account_name, videos_container_name, credential)
        album_file_names_future = executor.submit(all_album_file_names, account_name, table_name, credential)

        photos_result = photos_future.result()
        videos_result = videos_future.result()    
        album_file_names = set(album_file_names_future.result())
    
    non_album_photos = [photo for photo in photos_result if photo.filename not in album_file_names]
    non_album_videos = [video for video in videos_result if video.filename not in album_file_names]
    media_cache = merge(
        non_album_photos, non_album_videos,
        key=lambda m: m.last_modified,
        reverse=True)
    
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
