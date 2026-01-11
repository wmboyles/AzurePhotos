"""
API endpoints for handling videos.

:author: William Boyles
"""

from azure.identity import DefaultAzureCredential
from azure.storage.blob import ContainerClient, BlobProperties
from flask import Blueprint, redirect, request, current_app
from werkzeug.wrappers.response import Response
from src.lib.storage_helper import get_container_sas
from datetime import datetime

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

    account_name = current_app.config["account_name"]
    blob_account_url: str = f"https://{account_name}.blob.core.windows.net"
    credential: DefaultAzureCredential = current_app.config["credential"]
    videos_container_name: str = current_app.config["videos_container_name"]

    videos_container_sas: str = get_container_sas(account_name, videos_container_name, credential)

    return redirect(
        f"{blob_account_url}/{videos_container_name}/{filename}?{videos_container_sas}"
    )


def all_videos() -> list[tuple[datetime, str]]:
    """
    Get all vidoes stored in blob storage and their last modified time.
    Videos are ordered by their last modified time.
    """

    credential: DefaultAzureCredential = current_app.config["credential"]
    account_name = current_app.config["account_name"]
    blob_account_url: str = f"https://{account_name}.blob.core.windows.net"
    videos_container_name: str = current_app.config["videos_container_name"]

    with ContainerClient(
        blob_account_url, videos_container_name, credential
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
            ((last_modified(blob), str(blob.name)) for blob in blobs), reverse=True
        )
