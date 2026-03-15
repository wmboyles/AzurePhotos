"""
Generic API endpoints for handling any media.
Will delegate to the proper controller per media.
"""

from azure.identity import DefaultAzureCredential
from flask import Blueprint, redirect, current_app, request
from werkzeug.wrappers.response import Response
from werkzeug.datastructures.file_storage import FileStorage

import src.api.photos as photos
import src.api.videos as videos
from .media_cache import invalidates_media_cache

from ..lib.storage_helper import get_container_sas
from ..lib.models.media import MediaType, media_type_from_file_extension

from .albums import remove_from_all_albums, add_to_album

crud_controller = Blueprint(
    "crud_controller",
    __name__,
    template_folder="templates",
    static_folder="static",
    url_prefix="/",
)


@crud_controller.route("/thumbnail/<filename>", methods=["GET"])
def thumbnail(filename: str) -> Response:
    """
    Get the thumbnail for a photo or video.

    :param filename: The name of the file
    """

    media_type = media_type_from_file_extension(filename)
    match media_type:
        case MediaType.PHOTO:
            pass
        case MediaType.VIDEO:
            filename += ".webp"
        case _:
            raise ValueError(f"Unrecognized media type for {filename=}")

    account_name: str = current_app.config["account_name"]
    blob_account_url: str = f"https://{account_name}.blob.core.windows.net"
    credential: DefaultAzureCredential = current_app.config["credential"]
    thumbnails_container_name: str = current_app.config["thumbnails_container_name"]

    thumbnails_container_sas: str = get_container_sas(
        account_name, thumbnails_container_name, credential
    )
    response = redirect(
        f"{blob_account_url}/{thumbnails_container_name}/{filename}?{thumbnails_container_sas}"
    )
    response.headers["Cache-Control"] = "public, max-age=900"

    return response


@crud_controller.route("/fullsize/<filename>", methods=["GET"])
def fullsize(filename: str) -> Response:
    """
    Get the full size and resolution photo or video.

    :param filename: The name of the file.
    """

    media_type = media_type_from_file_extension(filename)
    match media_type:
        case MediaType.PHOTO:
            return photos.fullsize(filename)
        case MediaType.VIDEO:
            return videos.fullsize(filename)
        case _:
            raise ValueError(f"Unrecognized media type for {filename=}")


@crud_controller.route("/upload", methods=["POST"])
def upload() -> Response:
    """
    Upload a photo or video.
    """

    files = request.files.getlist("upload")
    dates_taken = request.form.getlist("dateTaken")

    if files is None or len(files) == 0:
        raise ValueError("No files provided for upload")
    if dates_taken is None or len(dates_taken) == 0:
        raise ValueError("No dates provided for uploaded items")
    if len(files) != len(dates_taken):
        raise ValueError("Number of uploaded files and number of dates do not match")

    _upload(*zip(files, dates_taken))

    return Response(status=201)

@invalidates_media_cache
def _upload(*file_infos: tuple[FileStorage, str]) -> list[str]:
    uploaded_filenames = list[str]()
    for file, date_taken in file_infos:
        media_type = media_type_from_file_extension(file.filename)
        match media_type:
            case MediaType.PHOTO:
                uploaded_photo = photos.upload((file, date_taken))
                uploaded_filenames.append(uploaded_photo)
            case MediaType.VIDEO:
                uploaded_video = videos.upload((file, date_taken))
                uploaded_filenames.append(uploaded_video)
            case _:
                raise ValueError(f"Unrecognized media type for {file.filename=}")

    return uploaded_filenames


# No invalidate media cache needed here because we upload directly to an album
@crud_controller.route("/upload/<album_name>", methods=["POST"])
def upload_to_album(album_name: str) -> Response:
    """
    Upload photos or videos, and add it to an album.
    """

    files = request.files.getlist("upload")
    dates_taken = request.form.getlist("dateTaken")

    if files is None or len(files) == 0:
        raise ValueError("No files provided for upload")
    if dates_taken is None or len(dates_taken) == 0:
        raise ValueError("No dates provided for uploaded items")
    if len(files) != len(dates_taken):
        raise ValueError("Number of uploaded files and number of dates do not match")

    uploaded_filenames = _upload(*zip(files, dates_taken))
    for uploaded_filename in uploaded_filenames:
        add_to_album_result = add_to_album(album_name, uploaded_filename)

        if (
            isinstance(add_to_album_result, Response)
            and add_to_album_result.status_code >= 400
        ):
            # TODO: Should we instead aggregate results at the end?
            return add_to_album_result

    return Response(status=201)

@crud_controller.route("/delete/<filename>", methods=["DELETE"])
@invalidates_media_cache
def delete(filename: str) -> Response:
    """
    Delete an entry from the storage account.
    Remove the entry, thumbnail, and all references to the photo in albums.

    :param filename: The name of the photo file
    """

    # Delete the main file + thumbnail
    media_type = media_type_from_file_extension(filename)
    match media_type:
        case MediaType.PHOTO:
            photos.delete_fullsize(filename)
            photos.delete_thumbnail(filename)
        case MediaType.VIDEO:
            videos.delete_fullsize(filename)
            videos.delete_thumbnail(filename)
        case _:
            raise ValueError(f"Unrecognized media type for {filename=}")

    remove_from_all_albums(filename)

    # Client JS code should remove image from view
    return Response(status=204)
