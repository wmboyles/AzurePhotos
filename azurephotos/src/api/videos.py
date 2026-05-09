"""
API endpoints for handling videos.

:author: William Boyles
"""

import os
import shutil
import tempfile
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

from azure.core.exceptions import ResourceNotFoundError
from azure.storage.blob import ContainerClient, ContentSettings
from flask import redirect, current_app
from werkzeug.utils import secure_filename
from werkzeug.wrappers.response import Response
from werkzeug.datastructures.file_storage import FileStorage

from ..lib.thumbnails import video_thumbnail as compute_thumbnail
from ..lib.storage_helper import get_container_sas

def fullsize(filename: str) -> Response:
    """
    Get a full resolution video.

    :param filename: The name of the file.
    """

    blob_account_url: str = current_app.config["blob_account_url"]
    videos_container_name: str = "videos"

    videos_container_sas = get_container_sas(videos_container_name)
    return redirect(
        f"{blob_account_url}/{videos_container_name}/{filename}?{videos_container_sas}"
    )


def upload(file: FileStorage, date_taken: datetime) -> str:
    """
    Upload videos to blob storage.

    :raises:
        ResourceExistsError when blob with filename already exists
    """

    videos_container_client: ContainerClient = current_app.config["videos_container_client"]
    thumbnails_container_client: ContainerClient = current_app.config["thumbnails_container_client"]

    save_filename = secure_filename(str(file.filename))
    metadata = {"lastModified": date_taken.isoformat()}

    with tempfile.NamedTemporaryFile(delete=False, suffix=".video") as temp_file:
        shutil.copyfileobj(file.stream, temp_file)   
        temp_file.flush()
        temp_path = temp_file.name       
    file_size = os.path.getsize(temp_path)                                  

    try:
        def upload_thumbnail(client: ContainerClient) -> None:
            thumbnail_bytes = compute_thumbnail(temp_path)
            _ = client.upload_blob(
                name=f"{save_filename}.webp",
                data=thumbnail_bytes,
                metadata=metadata,
                content_settings=ContentSettings(
                    cache_control="public, max-age=31536000, immutable"
                ),
            )

        def upload_fullsize(client: ContainerClient) -> None:
            with open(temp_path, "rb") as full:
                _ = client.upload_blob(
                    name=save_filename,
                    data=full,
                    length=file_size,
                    max_concurrency=4,
                    metadata=metadata
                )

        with ThreadPoolExecutor(max_workers=2) as executor:
            thumbnails_future = executor.submit(upload_thumbnail, thumbnails_container_client)
            fullsize_future = executor.submit(upload_fullsize, videos_container_client)

            # TODO: Try to delete thumbnail blob if fullsize upload failed
            thumbnails_future.result()
            fullsize_future.result()
    finally:
        try:
            os.remove(temp_path)
        except OSError:
            pass

    return save_filename


def delete_fullsize(filename: str) -> None:
    """
    Deletes the full length a video from the storage account.

    :param filename: The name of the video file
    """

    videos_container_client: ContainerClient = current_app.config["videos_container_client"]

    try:
        videos_container_client.delete_blob(filename)
    except ResourceNotFoundError:
        # Blob already deleted
        pass


def delete_thumbnail(filename: str) -> None:
    """
    Deletes the thumbnail photo from the storage account.

    :param filename: The name of the photo file
    """
    thumbnails_container_client: ContainerClient = current_app.config["thumbnails_container_client"]

    thumbnail_filename = filename + ".webp"

    try:
        thumbnails_container_client.delete_blob(thumbnail_filename)
    except ResourceNotFoundError:
        # Blob already deleted
        pass
