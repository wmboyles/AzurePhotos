"""
API endpoints for handling individual photos.

:author: William Boyles
"""

from io import BytesIO

from azure.core.exceptions import ResourceNotFoundError
from azure.storage.blob import ContainerClient, ContentSettings
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from flask import redirect, current_app
from werkzeug.utils import secure_filename
from werkzeug.wrappers.response import Response
from werkzeug.datastructures.file_storage import FileStorage

from ..lib.storage_helper import get_container_sas
from ..lib.thumbnails import thumbnail as compute_thumbnail

def fullsize(filename: str) -> Response:
    """
    Get the full-size image for a photo.
    Get the full-length video for a video.

    :param filename: The name of the file.
    """

    blob_account_url: str = current_app.config["blob_account_url"]
    photos_container_name: str = "photos"

    photos_container_sas: str = get_container_sas(photos_container_name)
    return redirect(
        f"{blob_account_url}/{photos_container_name}/{filename}?{photos_container_sas}"
    )


def delete_fullsize(filename: str) -> None:
    """
    Deletes the fullsize photo from the storage account.

    :param filename: The name of the photo file
    """

    photos_container_client: ContainerClient = current_app.config["photos_container_client"]

    try:
        photos_container_client.delete_blob(filename)
    except ResourceNotFoundError:
        # Blob already deleted
        pass


def delete_thumbnail(filename: str) -> None:
    """
    Deletes the thumbnail photo from the storage account.

    :param filename: The name of the photo file
    """

    thumbnails_container_client: ContainerClient = current_app.config["thumbnails_container_client"]

    try:
        thumbnails_container_client.delete_blob(filename)
    except ResourceNotFoundError:
        # Blob already deleted
        pass


def upload(file: FileStorage, date_taken: datetime) -> str:
    """
    Upload photos to blob storage.

    :raises:
        ResourceExistsError when blob with filename already exists
    """

    photos_container_client: ContainerClient = current_app.config["photos_container_client"]
    thumbnails_container_client: ContainerClient = current_app.config["thumbnails_container_client"]

    save_filename = secure_filename(str(file.filename))
    metadata = {"lastModified": date_taken.isoformat()}
    data = file.stream.read()

    def upload_thumbnail(client: ContainerClient) -> None:
        thumbnail = compute_thumbnail(BytesIO(data))
        client.upload_blob(
            name=save_filename,
            data=thumbnail,
            metadata=metadata,
            content_settings=ContentSettings(
                cache_control="public, max-age=31536000, immutable"
            )
        )

    def upload_fullsize(client: ContainerClient) -> None:
        client.upload_blob(
            name=save_filename,
            data=BytesIO(data),
            length=len(data),
            max_concurrency=4,
            metadata=metadata
        )

    photos_container_client: ContainerClient = current_app.config["photos_container_client"]
    thumbnails_container_client: ContainerClient = current_app.config["thumbnails_container_client"]

    with ThreadPoolExecutor(max_workers=2) as executor:
        thumbnail_future = executor.submit(upload_thumbnail, thumbnails_container_client)
        fullsize_future = executor.submit(upload_fullsize, photos_container_client)

        _ = thumbnail_future.result()
        _ = fullsize_future.result()
        # TODO: Try to delete thumbnail blob if fullsize upload failed

    return save_filename
