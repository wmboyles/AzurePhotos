"""
API endpoints for handling individual photos.

:author: William Boyles
"""

from azure.core.exceptions import ResourceNotFoundError
from azure.identity import DefaultAzureCredential
from azure.storage.blob import ContainerClient, BlobProperties, ContentSettings
from datetime import datetime
from flask import redirect, current_app
from werkzeug.utils import secure_filename
from werkzeug.wrappers.response import Response
from werkzeug.datastructures.file_storage import FileStorage

from ..lib.storage_helper import get_container_sas
from ..lib.thumbnails import thumbnail as compute_thumbnail
from ..lib.models.media import MediaRecord, MediaType


def fullsize(filename: str) -> Response:
    """
    Get the full-size image for a photo.
    Get the full-length video for a video.

    :param filename: The name of the file.
    """

    account_name: str = current_app.config["account_name"]
    blob_account_url: str = f"https://{account_name}.blob.core.windows.net"
    credential: DefaultAzureCredential = current_app.config["credential"]
    photos_container_name: str = current_app.config["photos_container_name"]

    photos_container_sas: str = get_container_sas(
        account_name, photos_container_name, credential
    )
    return redirect(
        f"{blob_account_url}/{photos_container_name}/{filename}?{photos_container_sas}"
    )


def delete_fullsize(filename: str) -> None:
    """
    Deletes the fullsize photo from the storage account.

    :param filename: The name of the photo file
    """

    account_name: str = current_app.config["account_name"]
    blob_account_url: str = f"https://{account_name}.blob.core.windows.net"
    photos_container_name: str = current_app.config["photos_container_name"]
    credential: DefaultAzureCredential = current_app.config["credential"]

    try:
        with ContainerClient(
            blob_account_url, photos_container_name, credential
        ) as photos_container_client:
            photos_container_client.delete_blob(filename)
    except ResourceNotFoundError:
        # Blob already deleted
        pass


def delete_thumbnail(filename: str) -> None:
    """
    Deletes the thumbnail photo from the storage account.

    :param filename: The name of the photo file
    """

    account_name: str = current_app.config["account_name"]
    blob_account_url: str = f"https://{account_name}.blob.core.windows.net"
    thumbnails_container_name: str = current_app.config["thumbnails_container_name"]
    credential: DefaultAzureCredential = current_app.config["credential"]

    try:
        with ContainerClient(
            blob_account_url, thumbnails_container_name, credential
        ) as thumbnails_container_client:
            thumbnails_container_client.delete_blob(filename)
    except ResourceNotFoundError:
        # Blob already deleted
        pass


def upload(file_info: tuple[FileStorage, str]) -> str:
    """
    Upload photos to blob storage.

    :raises:
        ResourceExistsError when blob with filename already exists
    """

    account_name: str = current_app.config["account_name"]
    blob_account_url: str = f"https://{account_name}.blob.core.windows.net"
    photos_container_name: str = current_app.config["photos_container_name"]
    thumbnails_container_name: str = current_app.config["thumbnails_container_name"]
    credential: DefaultAzureCredential = current_app.config["credential"]

    file, modified_date = file_info
    save_filename = secure_filename(str(file.filename))
    metadata = {"lastModified": modified_date}  # ISO timestamp
    with ContainerClient(
        blob_account_url, photos_container_name, credential
    ) as photos_container_client, ContainerClient(
        blob_account_url, thumbnails_container_name, credential
    ) as thumbnails_container_client:
        _ = thumbnails_container_client.upload_blob(
            name=save_filename,
            data=compute_thumbnail(file.stream),
            metadata=metadata,
            content_settings=ContentSettings(
                cache_control="public, max-age=31536000, immutable"
            ),
        )

        if file.stream.seekable():
            file.stream.seek(0)

        _ = photos_container_client.upload_blob(
            name=save_filename, data=file.stream, metadata=metadata
        )

        # TODO: Try to delete thumbnail blob if fullsize upload failed

    return save_filename


def all_photos(
    account_name: str, photos_container_name: str, credential: DefaultAzureCredential
) -> list[MediaRecord]:
    """
    Get all photos stored in blob storage and their last modified time.
    Photos are ordered by their last modified time.
    """

    # credential: DefaultAzureCredential = current_app.config["credential"]
    # account_name = current_app.config["account_name"]
    blob_account_url: str = f"https://{account_name}.blob.core.windows.net"
    # photos_container_name: str = current_app.config["photos_container_name"]

    with ContainerClient(
        blob_account_url, photos_container_name, credential
    ) as container_client:
        blobs = list(container_client.list_blobs(include="metadata"))

    def last_modified(blob_properties: BlobProperties) -> datetime:
        if (
            not blob_properties.metadata
            or not isinstance(blob_properties.metadata, dict)
            or not blob_properties.metadata.get("lastModified")
        ):
            return blob_properties.last_modified  # type: ignore

        return datetime.fromisoformat(blob_properties.metadata["lastModified"])

    return sorted(
        (
            MediaRecord(
                last_modified=last_modified(blob),
                filename=str(blob.name),
                type=MediaType.PHOTO,
            )
            for blob in blobs
        ),
        reverse=True,
    )
