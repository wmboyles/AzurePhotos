"""
API endpoints for managing albums.

Albums are stored in Azure Table Storage.
The partition key is the album name, and the row key is the photo filename.
An empty row key represents the album itself.

:author: William Boyles
"""

from datetime import datetime, timezone
from azure.core.exceptions import ResourceNotFoundError, ResourceExistsError
from flask import Blueprint, Response, current_app, url_for, redirect
from typing import Any

from ..storage_helper import get_table_client

api_albums_controller = Blueprint(
    "api_albums_controller",
    __name__,
    template_folder="templates",
    static_folder="static",
    url_prefix="/api/albums",
)


@api_albums_controller.route("/<album_name>", methods=["POST"])
def create_album(album_name: str) -> Response | dict[str, Any]:
    """
    Create a new album.

    :param album_name: The name of the album to create. Must be unique.
    """

    account_name = current_app.config["account_name"]
    table_name = current_app.config["albums_table_name"]
    credential = current_app.config["credential"]
    table_client = get_table_client(account_name, table_name, credential)

    new_album = {
        "PartitionKey": album_name,
        "RowKey": "",
        "Created": datetime.now(timezone.utc),
    }

    try:
        return table_client.create_entity(new_album)  # type: ignore
    except ResourceExistsError:
        return Response("Album already exists", status=409)


@api_albums_controller.route("/albums", methods=["GET"])
def list_albums() -> list[str]:
    """
    List all album names.
    """

    account_name = current_app.config["account_name"]
    table_name = current_app.config["albums_table_name"]
    credential = current_app.config["credential"]
    table_client = get_table_client(account_name, table_name, credential)

    entities = table_client.query_entities(query_filter="RowKey eq ''")
    return [row["PartitionKey"] for row in entities]


@api_albums_controller.route("/<album_name>/rename/<new_name>", methods=["PUT"])
def rename_album(album_name: str, new_name: str) -> Response:
    """
    Rename an album.

    :param album_name: The name of the album to rename.
    :param new_name: The new name for the album.
    """

    """
    Since we can't actually update the partition key, we create a copy of the
    old album with the new name and then delete the old album.
    """

    account_name = current_app.config["account_name"]
    table_name = current_app.config["albums_table_name"]
    credential = current_app.config["credential"]
    table_client = get_table_client(account_name, table_name, credential)

    query = "PartitionKey eq @album_name"
    parameters = {"album_name": album_name}
    entities = table_client.query_entities(query_filter=query, parameters=parameters)
    for entity in entities:
        photo_copy = {
            "PartitionKey": new_name,
            "RowKey": entity["RowKey"],
            "Created": entity["Created"],
        }
        table_client.create_entity(photo_copy)
        table_client.delete_entity(entity["PartitionKey"], entity["RowKey"])

    return Response(status=204)


@api_albums_controller.route("<album_name>", methods=["DELETE"])
def delete_album(album_name: str):
    """
    Delete an album.
    This does not delete the photos in the album.

    :param album_name: The name of the album to delete.
    """

    account_name = current_app.config["account_name"]
    table_name = current_app.config["albums_table_name"]
    credential = current_app.config["credential"]
    table_client = get_table_client(account_name, table_name, credential)

    query = "PartitionKey eq @album_name"
    parameters = {"album_name": album_name}
    entities = table_client.query_entities(query_filter=query, parameters=parameters)
    for entity in entities:
        table_client.delete_entity(entity["PartitionKey"], entity["RowKey"])

    # TODO: Check if the album was actually deleted
    return Response(status=204)


@api_albums_controller.route("<album_name>/<filename>", methods=["POST"])
def add_to_album(album_name: str, filename: str) -> Response | dict[str, Any]:
    """
    Add a photo to an album.

    :param album_name: The name of the album to add the photo to.
    :param filename: The filename of the photo to add to the album.
    """

    account_name = current_app.config["account_name"]
    table_name = current_app.config["albums_table_name"]
    credential = current_app.config["credential"]
    table_client = get_table_client(account_name, table_name, credential)

    try:
        table_client.get_entity(partition_key=album_name, row_key="")
    except ResourceNotFoundError:
        return Response("Album does not exist", status=404)

    new_photo = {
        "PartitionKey": album_name,
        "RowKey": filename,
        "Created": datetime.now(timezone.utc),
    }
    return table_client.create_entity(new_photo)  # type: ignore


@api_albums_controller.route("<album_name>", methods=["GET"])
def list_album(album_name: str) -> Response | list[str]:
    """
    List the photos in an album.

    :param album_name: The name of the album to list photos for.
    """

    account_name = current_app.config["account_name"]
    table_name = current_app.config["albums_table_name"]
    credential = current_app.config["credential"]
    table_client = get_table_client(account_name, table_name, credential)

    query = "PartitionKey eq @album_name"
    parameters = {"album_name": album_name}
    entities = list(
        table_client.query_entities(query_filter=query, parameters=parameters)
    )
    if len(entities) == 0:
        return Response("Album does not exist", status=404)

    return [entity["RowKey"] for entity in entities if entity["RowKey"] != ""]


@api_albums_controller.route("<album_name>/<filename>", methods=["DELETE"])
def remove_from_album(album_name: str, filename: str) -> Response:
    """
    Remove a photo from an album.
    This does not remove the photo itself or remove it from other albums.

    :param album_name: The name of the album to remove the photo from.
    :param filename: The filename of the photo to remove from the album.
    """

    account_name = current_app.config["account_name"]
    table_name = current_app.config["albums_table_name"]
    credential = current_app.config["credential"]
    table_client = get_table_client(account_name, table_name, credential)

    table_client.delete_entity(partition_key=album_name, row_key=filename)
    return Response(status=204)


@api_albums_controller.route("thumbnail/<album_name>", methods=["GET"])
def get_album_thumbnail(album_name: str) -> Response:
    """
    Get the thumbnail for an album.

    :param album_name: The name of the album to get the thumbnail for.
    """

    # Select a random photo from the album to use as the thumbnail
    album_photos = list_album(album_name)
    if isinstance(album_photos, Response) and album_photos.status_code == 404:
        return album_photos
    elif not isinstance(album_photos, list):
        return Response("Internal server error", status=500)
    elif len(album_photos) == 0:
        print("Trying to serve static photo_album-512.webp")
        return redirect("/static/photo_album-512.webp")  # type: ignore

    thumbnail_filename = album_photos[0]
    return redirect(
        url_for("api_photos_controller.thumbnail", filename=thumbnail_filename)
    )  # type: ignore


def remove_from_all_albums(filename: str) -> None:
    """
    Remove a photo from all albums.
    Most likely used when deleting a photo.

    :param filename: The filename of the photo to remove.
    """

    account_name = current_app.config["account_name"]
    table_name = current_app.config["albums_table_name"]
    credential = current_app.config["credential"]
    table_client = get_table_client(account_name, table_name, credential)

    query = "RowKey eq @filename"
    parameters = {"filename": filename}
    entities = table_client.query_entities(query_filter=query, parameters=parameters)
    for entity in entities:
        table_client.delete_entity(entity)


def all_album_photos() -> list[str]:
    """
    List all photo names in all albums.
    Note that photos in multiple albums will be listed multiple times.
    """

    account_name = current_app.config["account_name"]
    table_name = current_app.config["albums_table_name"]
    credential = current_app.config["credential"]
    table_client = get_table_client(account_name, table_name, credential)

    entities = table_client.query_entities(query_filter="RowKey ne ''")
    return [row["RowKey"] for row in entities]
