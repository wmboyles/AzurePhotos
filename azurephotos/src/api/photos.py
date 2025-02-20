"""
API endpoints for handling individual photos.

:author: William Boyles
"""

from azure.core.async_paging import AsyncItemPaged
from azure.core.exceptions import ResourceNotFoundError
from azure.identity.aio import DefaultAzureCredential
from azure.storage.blob.aio import ContainerClient
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
async def thumbnail(filename: str) -> Response:
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
async def fullsize(filename: str) -> Response:
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
async def delete(filename: str) -> Response:
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
        thumbnail_container_client = ContainerClient(
            blob_account_url, thumbnails_container_name, credential
        )
        async with thumbnail_container_client:
            await thumbnail_container_client.delete_blob(filename)

        photos_container_client = ContainerClient(
            blob_account_url, photos_container_name, credential
        )
        async with photos_container_client:
            await photos_container_client.delete_blob(filename)

        await remove_from_all_albums(filename)
    except ResourceNotFoundError as e:
        return Response(e.message, status=404)

    # Client JS code should remove image from view
    return Response(status=200)


async def _upload() -> str:
    blob_account_url: str = current_app.config["blob_account_url"]
    photos_container_name: str = current_app.config["photos_container_name"]
    credential = current_app.config["credential"]

    container_client = ContainerClient(
        blob_account_url, photos_container_name, credential
    )
    async with container_client:
        files = request.files.getlist("upload")
        for file in files:
            save_filename = secure_filename(str(file.filename))
            await container_client.upload_blob(save_filename, file.stream)

    return save_filename


@api_photos_controller.route("/upload", methods=["POST"])
async def upload() -> Response:
    """
    Upload a photo to the storage account.
    Creating the thumbnail is handled by the resizer function.
    """

    _ = _upload()

    # TODO: Allow uploading photos without refreshing the page
    return redirect("/")


@api_photos_controller.route("/upload/<album_name>", methods=["POST"])
async def upload_to_album(album_name: str) -> Response:
    upload_filename = await _upload()
    add_to_album_result = await add_to_album(album_name, upload_filename)

    if (
        isinstance(add_to_album_result, Response)
        and add_to_album_result.status_code >= 400
    ):
        return add_to_album_result

    # TODO: Allow uploading photos without refreshing the page
    return redirect(f"/albums/{album_name}")


async def list_all_photos() -> AsyncItemPaged[str]:
    """
    Get all photo names stored in blob storage.
    """

    credential: DefaultAzureCredential = current_app.config["credential"]
    blob_account_url: str = current_app.config["blob_account_url"]
    photos_container_name: str = current_app.config["photos_container_name"]

    container_client = ContainerClient(
        blob_account_url, photos_container_name, credential  # type: ignore aio credential
    )
    return container_client.list_blob_names()
