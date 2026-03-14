from flask import Blueprint, render_template, Response
from typing import Sequence

from ..api.albums import list_albums, list_album, all_album_file_names
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
    album_file_names = set(all_album_file_names())
    non_album_photos = [photo for photo in all_photos() if photo.filename not in album_file_names]
    non_album_videos = [video for video in all_videos() if video.filename not in album_file_names]
    media: Sequence[MediaRecord] = merge(
        non_album_photos, non_album_videos,
        key=lambda m: m.last_modified,
        reverse=True)
    album_names = list_albums()
    return render_template("photos.html", medias=media, albums=album_names)

@albums_view_controller.route("/<album_name>", methods=["GET"])
def album(album_name: str) -> str | Response:
    files_in_album = list_album(album_name)
    if isinstance(files_in_album, Response):
        return files_in_album
    
    return render_template("album.html", album=album_name, medias=files_in_album)
