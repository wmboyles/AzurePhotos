"""
API endpoints for handling videos.

:author: William Boyles
"""

from azure.core.exceptions import ResourceNotFoundError
from azure.identity import DefaultAzureCredential
from azure.storage.blob import ContainerClient, BlobProperties
from datetime import datetime
from flask import Blueprint, redirect, request, current_app
from werkzeug.utils import secure_filename
from werkzeug.wrappers.response import Response
from werkzeug.datastructures.file_storage import FileStorage

from ..lib.storage_helper import get_container_sas
from ..lib.models.media import VideoRecord

api_videos_controller = Blueprint(
    "api_videos_controller",
    __name__,
    template_folder="templates",
    static_folder="static",
    url_prefix="/api/videos",
)


@api_videos_controller.route("/<filename>", methods=["GET"])
def video(filename: str) -> Response:
    """
    Get the SAS for the full-size video.

    :param filename: The name of the video file.
    """

    account_name: str = current_app.config["account_name"]
    blob_account_url: str = f"https://{account_name}.blob.core.windows.net"
    credential: DefaultAzureCredential = current_app.config["credential"]
    videos_container_name: str = current_app.config["videos_container_name"]

    videos_container_sas: str = get_container_sas(account_name, videos_container_name, credential)

    return redirect(f"{blob_account_url}/{videos_container_name}/{filename}?{videos_container_sas}")


def all_videos() -> list[VideoRecord]:
    """
    Get all vidoes stored in blob storage and their last modified time.
    Videos are ordered by their last modified time.
    """

    credential: DefaultAzureCredential = current_app.config["credential"]
    account_name = current_app.config["account_name"]
    blob_account_url: str = f"https://{account_name}.blob.core.windows.net"
    videos_container_name: str = current_app.config["videos_container_name"]

    with ContainerClient(blob_account_url, videos_container_name, credential) as container_client:
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
                VideoRecord(last_modified=last_modified(blob), filename=str(blob.name))
                for blob in blobs
            ),
            reverse=True,
        )


def _upload(*file_info: tuple[FileStorage, str]) -> list[str]:
    """
    Upload videos to blob storage.

    :param file_info: Collection if files and their last modified time as an ISO-formatted datetime
    :type file_info: tuple[FileStorage, str]
    :return: List of uploaded file names
    :rtype: list[str]
    """

    if not file_info:
        raise Exception("No files to upload")

    account_name: str = current_app.config["account_name"]
    blob_account_url: str = f"https://{account_name}.blob.core.windows.net"
    videos_container_name: str = current_app.config["videos_container_name"]
    credential: DefaultAzureCredential = current_app.config["credential"]

    save_filenames = list[str]()
    with ContainerClient(blob_account_url, videos_container_name, credential) as container_client:
        for file, modified_date in file_info:
            save_filename = secure_filename(str(file.filename))
            metadata = {
                "lastModified": modified_date # ISO timestamp
            }

            container_client.upload_blob(save_filename, file.stream, metadata=metadata)

            # TODO: Compute video thumbnail

            save_filenames.append(save_filename)

    if not save_filenames:
        raise Exception("Could not upload file")

    return save_filenames


@api_videos_controller.route("/upload", methods=["POST"])
def upload() -> Response:
    """
    Uploads videos to the storage account.
    """

    # TODO: Is this method needed anymore?

    files = request.files.getlist("upload")
    datesTaken = request.form.getlist("dateTaken")

    _ = _upload(*zip(files, datesTaken))

    return Response(status=201)

@api_videos_controller.route("/delete/<filename>", methods=["DELETE"])
def delete(filename: str) -> Response:
    """
    Delete a video from the storage account.
    
    :param filename: The name of the video file
    :type filename: str
    :return: 204 Response if successful; 404 for missing file; throws otherwise
    :rtype: Response
    """

    account_name: str = current_app.config["account_name"]
    blob_account_url: str = f"https://{account_name}.blob.core.windows.net"
    videos_container_name: str = current_app.config["videos_container_name"]
    credential: DefaultAzureCredential = current_app.config["credential"]

    try:
        with ContainerClient(blob_account_url, videos_container_name, credential) as container_client:
            container_client.delete_blob(filename)
    except ResourceNotFoundError as e:
        return Response(e.message, status=404)

    # Client JS code should remove video from view
    return Response(status=204)
