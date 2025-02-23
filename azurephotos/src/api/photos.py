"""
API endpoints for handling individual photos.

:author: William Boyles
"""

from azure.core.exceptions import ResourceNotFoundError
from azure.core.paging import ItemPaged
from azure.identity import DefaultAzureCredential
from azure.storage.blob import ContainerClient
from flask import Blueprint, redirect, request, current_app
from werkzeug.utils import secure_filename
from werkzeug.wrappers.response import Response

from .albums import remove_from_all_albums, add_to_album

api_photos_controller = Blueprint(
    "api_photos_controller",
    __name__,
    template_folder="templates",
    static_folder="static",
    url_prefix="/",
)


@api_photos_controller.route("/thumbnail/<filename>", methods=["GET"])
def thumbnail(filename: str) -> Response:
    """
    Get the thumbnail image for a photo.

    :param filename: The name of the photo file.
    """

    blob_account_url: str = current_app.config["blob_account_url"]
    thumbnails_container_name: str = current_app.config["thumbnails_container_name"]
    thumbnails_container_sas: str = current_app.config["thumbnails_container_sas"]

    return redirect(
        f"{blob_account_url}/{thumbnails_container_name}/{filename}?{thumbnails_container_sas}"
    )


@api_photos_controller.route("/fullsize/<filename>", methods=["GET"])
def fullsize(filename: str) -> Response:
    """
    Get the full-size image for a photo.

    :param filename: The name of the photo file.
    """

    blob_account_url: str = current_app.config["blob_account_url"]
    photos_container_name: str = current_app.config["photos_container_name"]
    photos_container_sas: str = current_app.config["photos_container_sas"]

    return redirect(
        f"{blob_account_url}/{photos_container_name}/{filename}?{photos_container_sas}"
    )


@api_photos_controller.route("/delete/<filename>", methods=["DELETE"])
def delete(filename: str) -> Response:
    """
    Delete a photo from the storage account.
    Removes the photo, thumbnail, and all references to the photo in albums.

    :param filename: The name of the photo file.
    """

    blob_account_url: str = current_app.config["blob_account_url"]
    thumbnails_container_name: str = current_app.config["thumbnails_container_name"]
    photos_container_name: str = current_app.config["photos_container_name"]
    credential = current_app.config["credential"]

    try:
        with ContainerClient(blob_account_url, thumbnails_container_name, credential) as thumbnail_container_client:
            thumbnail_container_client.delete_blob(filename)

        with ContainerClient(blob_account_url, photos_container_name, credential) as photos_container_client:
            photos_container_client.delete_blob(filename)

        remove_from_all_albums(filename)
    except ResourceNotFoundError as e:
        return Response(e.message, status=404)

    # Client JS code should remove image from view
    return Response(status=200)


def _upload() -> str:
    blob_account_url: str = current_app.config["blob_account_url"]
    photos_container_name: str = current_app.config["photos_container_name"]
    credential = current_app.config["credential"]

    save_filename: str | None = None
    with ContainerClient(blob_account_url, photos_container_name, credential) as container_client:
        for file in request.files.getlist("upload"):
            save_filename = secure_filename(str(file.filename))
            container_client.upload_blob(save_filename, file.stream)

    if save_filename is None:
        raise Exception("Could not upload file")
    
    return save_filename


@api_photos_controller.route("/upload", methods=["POST"])
def upload() -> Response:
    """
    Upload a photo to the storage account.
    Creating the thumbnail is handled by the resizer function.
    """

    _ = _upload()

    # TODO: Allow uploading photos without refreshing the page
    return redirect("/")


@api_photos_controller.route("/upload/<album_name>", methods=["POST"])
def upload_to_album(album_name: str) -> Response:
    upload_filename = _upload()
    add_to_album_result = add_to_album(album_name, upload_filename)

    if (
        isinstance(add_to_album_result, Response)
        and add_to_album_result.status_code >= 400
    ):
        return add_to_album_result

    # TODO: Allow uploading photos without refreshing the page
    return redirect(f"/albums/{album_name}")


def all_photos() -> list[str]:
    """
    Get all photo names stored in blob storage.
    """

    credential: DefaultAzureCredential = current_app.config["credential"]
    blob_account_url: str = current_app.config["blob_account_url"]
    photos_container_name: str = current_app.config["photos_container_name"]

    with ContainerClient(blob_account_url, photos_container_name, credential) as container_client:
        return list(container_client.list_blob_names())
