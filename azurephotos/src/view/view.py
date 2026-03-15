from azure.identity import DefaultAzureCredential
from concurrent.futures import ThreadPoolExecutor
from flask import Blueprint, render_template, Response, current_app
from typing import Sequence

from ..api.albums import _list_albums, list_album, all_album_file_names
from ..api.photos import all_photos
from ..api.videos import all_videos
from ..lib.models.media import MediaRecord
from ..lib.sorting import merge

landing_view_controller = Blueprint(
    "landing_view_controller",
    __name__,
    template_folder="templates",
    static_folder="static",
    url_prefix="/",
)

albums_view_controller = Blueprint(
    "albums_view_controller",
    __name__,
    template_folder="templates",
    static_folder="static",
    url_prefix="/albums",
)

blueprints = {
    landing_view_controller,
    albums_view_controller,
}

@landing_view_controller.route("/", methods=["GET"])
def main() -> str:
    account_name: str = current_app.config["account_name"]
    photos_container_name: str = current_app.config["photos_container_name"]
    videos_container_name: str = current_app.config["videos_container_name"]
    table_name: str = current_app.config["albums_table_name"]
    credential: DefaultAzureCredential = current_app.config["credential"]

    with ThreadPoolExecutor() as executor:
        photos_future = executor.submit(all_photos, account_name, photos_container_name, credential)
        videos_future = executor.submit(all_videos, account_name, videos_container_name, credential)
        album_file_names_future = executor.submit(all_album_file_names, account_name, table_name, credential)
        album_names_future = executor.submit(_list_albums, account_name, table_name, credential)

        photos = photos_future.result()
        videos = videos_future.result()    
        album_file_names = set(album_file_names_future.result())
        album_names = album_names_future.result()
    
    non_album_photos = [photo for photo in photos if photo.filename not in album_file_names]
    non_album_videos = [video for video in videos if video.filename not in album_file_names]
    media: Sequence[MediaRecord] = merge(
        non_album_photos, non_album_videos,
        key=lambda m: m.last_modified,
        reverse=True)

    return render_template("photos.html", medias=media, albums=album_names)

@albums_view_controller.route("/<album_name>", methods=["GET"])
def album(album_name: str) -> str | Response:
    files_in_album = list_album(album_name)
    if isinstance(files_in_album, Response):
        return files_in_album
    
    return render_template("album.html", album=album_name, medias=files_in_album)
