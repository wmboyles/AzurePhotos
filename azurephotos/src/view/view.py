from flask import Blueprint, render_template

from ..api.albums import list_albums, list_album, all_album_photos
from ..api.photos import all_photos
from ..api.videos import all_videos

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

videos_view_controller = Blueprint(
    "video_view_controller",
    __name__,
    template_folder="templates",
    static_folder="static",
    url_prefix="/videos"
)

blueprints = {
    landing_view_controller,
    albums_view_controller,
    videos_view_controller
}


def non_album_photos() -> list[str]:
    """
    Get all photos that are not in any photo album.
    Photos are sorted in order of their lastModified date.
    """

    album_photos = set(all_album_photos())
    return [photo for (_, photo) in all_photos() if photo not in album_photos]

@landing_view_controller.route("/")
def photos() -> str:
    image_names = non_album_photos()
    album_names = list_albums()
    return render_template("photos.html", images=image_names, albums=album_names)


@albums_view_controller.route("/<album_name>", methods=["GET"])
def album(album_name: str) -> str:
    images_in_album = list_album(album_name)
    return render_template("album.html", album=album_name, images=images_in_album)

@videos_view_controller.route("/")
def videos() -> str:
    videos = [video for (_, video) in all_videos()]

    # TODO: Albums with videos
    return render_template("videos.html", videos=videos)