from datetime import datetime
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


def non_album_photos() -> list[tuple[datetime, str]]:
    """
    Get all photos that are not in any album.
    Photos are sorted in order of their lastModified date, descending.

    :return: Collection of photo last modified time and name
    :rtype: list[tuple[datetime, str]]
    """

    album_photos = set(all_album_photos())
    return [(last_modified, photo) for (last_modified, photo) in all_photos() if photo not in album_photos]

def non_album_videos() -> list[tuple[datetime, str]]:
    """
    Get all videos that are not in any album.
    Videos are sorted in order of the lastModified date, descending.
    
    :return: Collection of video last modified time and name
    :rtype: list[tuple[datetime, str]]
    """

    album_videos = set[str]() # TODO: Allow videos in photo albums
    return [(last_modified, video) for (last_modified, video) in all_videos() if video not in album_videos]

@landing_view_controller.route("/")
def photos() -> str:
    # Merge photos and videos together
    photos, videos = non_album_photos(), non_album_videos()
    media = []
    photos_index, videos_index = 0, 0
    while photos_index < len(photos) and videos_index < len(videos):
        photo_last_modified, photo_name = photos[photos_index]
        video_last_modified, video_name = videos[videos_index]

        if photo_last_modified >= video_last_modified:
            media.append({
                "filename": photo_name,
                "type": "photo",
                "last_modified": photo_last_modified
            })
            photos_index += 1
        else:
            media.append({
                "filename": video_name,
                "type": "video",
                "last_modified": video_last_modified
            })
            videos_index += 1
    while photos_index < len(photos):
        photo_last_modified, photo_name = photos[photos_index]
        media.append({
                "filename": photo_name,
                "type": "photo",
                "last_modified": photo_last_modified
            })
        photos_index += 1
    while videos_index < len(videos):
        video_last_modified, video_name = videos[videos_index]
        media.append({
                "filename": video_name,
                "type": "video",
                "last_modified": video_last_modified
            })
        videos_index += 1

    album_names = list_albums()
    return render_template("photos.html", medias=media, albums=album_names)


@albums_view_controller.route("/<album_name>", methods=["GET"])
def album(album_name: str) -> str:
    images_in_album = list_album(album_name)
    return render_template("album.html", album=album_name, images=images_in_album)

@videos_view_controller.route("/")
def videos() -> str:
    videos = [video for (_, video) in non_album_videos()]

    # TODO: Albums with videos
    return render_template("videos.html", videos=videos)