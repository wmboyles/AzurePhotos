from flask import Blueprint, render_template
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

def non_album_photos() -> list[MediaRecord]:
    """
    Get all photos that are not in any album.
    Photos are sorted in order of their lastModified date, descending.

    :return: Collection of photo last modified time and name
    :rtype: list[tuple[datetime, str]]
    """

    album_file_names = set(all_album_file_names())
    return [photo for photo in all_photos() if photo.filename not in album_file_names]

def non_album_videos() -> list[MediaRecord]:
    """
    Get all videos that are not in any album.
    Videos are sorted in order of the lastModified date, descending.
    
    :return: Collection of video last modified time and name
    :rtype: list[tuple[datetime, str]]
    """

    album_file_names = set(all_album_file_names())
    return [video for video in all_videos() if video not in album_file_names]

@landing_view_controller.route("/", methods=["GET"])
def main() -> str:
    media: Sequence[MediaRecord] = merge(
        non_album_photos(),
        non_album_videos(),
        key=lambda m: m.last_modified,
        reverse=True)
    album_names = list_albums()
    return render_template("photos.html", medias=media, albums=album_names)

@albums_view_controller.route("/<album_name>", methods=["GET"])
def album(album_name: str) -> str:
    files_in_album = list_album(album_name)
    return render_template("album.html", album=album_name, medias=files_in_album)
