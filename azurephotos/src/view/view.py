from flask import Blueprint, render_template
import asyncio

from ..api.albums import list_albums, list_album, list_all_album_photos
from ..api.photos import list_all_photos

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


async def list_non_album_photos() -> list[str]:
    """
    Get all photos that are not in any photo album.
    """

    all_album_photos = set()
    async for album_photo in await list_all_album_photos():
        all_album_photos.add(album_photo)

    all_photos = await list_all_photos()

    return [photo async for photo in all_photos if photo not in all_album_photos]


@landing_view_controller.route("/")
def index():
    image_names = asyncio.run(list_non_album_photos())
    album_names = asyncio.run(list_albums())
    return render_template("index.html", images=image_names, albums=album_names)


@albums_view_controller.route("/<album_name>", methods=["GET"])
def album(album_name: str):
    images_in_album = asyncio.run(list_album(album_name))
    return render_template("album.html", album=album_name, images=images_in_album)
