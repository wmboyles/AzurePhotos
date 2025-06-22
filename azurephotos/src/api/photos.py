"""
API endpoints for handling individual photos.

:author: William Boyles
"""

from azure.core.exceptions import ResourceNotFoundError
from azure.identity import DefaultAzureCredential
from azure.storage.blob import ContainerClient, BlobProperties
from flask import Blueprint, redirect, request, current_app
from werkzeug.utils import secure_filename
from werkzeug.wrappers.response import Response
from werkzeug.datastructures.file_storage import FileStorage
from src.lib.storage_helper import get_container_sas
from src.lib.thumbnails import thumbnail as compute_thumbnail
from datetime import datetime

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

    account_name = current_app.config["account_name"]
    blob_account_url: str = f"https://{account_name}.blob.core.windows.net"
    credential: DefaultAzureCredential = current_app.config["credential"]
    thumbnails_container_name: str = current_app.config["thumbnails_container_name"]
    
    thumbnails_container_sas: str = get_container_sas(account_name, thumbnails_container_name, credential)

    return redirect(
        f"{blob_account_url}/{thumbnails_container_name}/{filename}?{thumbnails_container_sas}"
    )


@api_photos_controller.route("/fullsize/<filename>", methods=["GET"])
def fullsize(filename: str) -> Response:
    """
    Get the full-size image for a photo.

    :param filename: The name of the photo file.
    """

    account_name = current_app.config["account_name"]
    blob_account_url: str = f"https://{account_name}.blob.core.windows.net"
    credential: DefaultAzureCredential = current_app.config["credential"]
    photos_container_name: str = current_app.config["photos_container_name"]

    photos_container_sas: str = get_container_sas(account_name, photos_container_name, credential)

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

    account_name: str = current_app.config["account_name"]
    blob_account_url: str = f"https://{account_name}.blob.core.windows.net"
    thumbnails_container_name: str = current_app.config["thumbnails_container_name"]
    photos_container_name: str = current_app.config["photos_container_name"]
    credential = current_app.config["credential"]

    try:
        with ContainerClient(blob_account_url, photos_container_name, credential) as photos_container_client:
            photos_container_client.delete_blob(filename)

        remove_from_all_albums(filename)
    except ResourceNotFoundError as e:
        return Response(e.message, status=404)

    # Ignore if removing thumbnail fails 
    try:
        with ContainerClient(blob_account_url, thumbnails_container_name, credential) as thumbnail_container_client:
            thumbnail_container_client.delete_blob(filename)
    except ResourceNotFoundError as e:
        pass

    # Client JS code should remove image from view
    return Response(status=204)


def _upload(*file_info: tuple[FileStorage, str]) -> list[str]:
    """
    Upload photos to blob storage.
    Also, compute and upload thunbnails.

    :param file_info: Collection of files and their last modified time as an ISO-formatted datetime

    :returns: List of uploaded file names
    """

    if not file_info:
        raise Exception("No files to upload")

    account_name = current_app.config["account_name"]
    blob_account_url: str = f"https://{account_name}.blob.core.windows.net"
    photos_container_name: str = current_app.config["photos_container_name"]
    thumbnails_container_name: str = current_app.config["thumbnails_container_name"]
    credential = current_app.config["credential"]

    save_filenames = list[str]()
    with ContainerClient(blob_account_url, photos_container_name, credential) as fullsize_container_client, ContainerClient(blob_account_url, thumbnails_container_name, credential) as thumbnails_container_client:
        for (file, modified_date) in file_info:
            save_filename = secure_filename(str(file.filename))
            metadata = {
                "lastModified": modified_date # ISO timestamp
            }

            fullsize_container_client.upload_blob(save_filename, file.stream, metadata=metadata)

            thumbnail_bytes = compute_thumbnail(file.stream)
            thumbnails_container_client.upload_blob(save_filename, thumbnail_bytes.getvalue(), metadata=metadata)

            save_filenames.append(save_filename)

    if not save_filenames:
        raise Exception("Could not upload file")
    
    return save_filenames


@api_photos_controller.route("/upload", methods=["POST"])
def upload() -> Response:
    """
    Upload photos to the storage account.
    """

    files = request.files.getlist("upload")
    datesTaken = request.form.getlist("dateTaken")

    _ = _upload(*zip(files,datesTaken))

    return Response(status=201)


@api_photos_controller.route("/upload/<album_name>", methods=["POST"])
def upload_to_album(album_name: str) -> Response:
    """
    Upload photos and add it to an album together
    """
    
    files = request.files.getlist("upload")
    datesTaken = request.form.getlist("dateTaken")
    
    upload_filenames = _upload(*zip(files,datesTaken))

    for upload_filename in upload_filenames:
        add_to_album_result = add_to_album(album_name, upload_filename)

        if isinstance(add_to_album_result, Response) and add_to_album_result.status_code >= 400:
            return add_to_album_result

    return Response(status=201)


def all_photos() -> list[tuple[datetime, str]]:
    """
    Get all photos stored in blob storage and their last modified time.
    Photos are ordered by their last modified time.
    """

    credential: DefaultAzureCredential = current_app.config["credential"]
    account_name = current_app.config["account_name"]
    blob_account_url: str = f"https://{account_name}.blob.core.windows.net"
    photos_container_name: str = current_app.config["photos_container_name"]

    
    with ContainerClient(blob_account_url, photos_container_name, credential) as container_client:
        blobs = list(container_client.list_blobs(include="metadata"))

        def last_modified(blob_properties: BlobProperties) -> datetime:
            if not blob_properties.metadata or not isinstance(blob_properties.metadata, dict) or not blob_properties.metadata.get("lastModified"):
                return blob_properties.last_modified # type: ignore
            
            return datetime.fromisoformat(blob_properties.metadata["lastModified"])

        return sorted(((last_modified(blob), str(blob.name)) for blob in blobs))
