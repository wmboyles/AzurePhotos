"""
API endpoints for managing albums.

Albums are stored in Azure Table Storage.
The partition key is the album name, and the row key is the photo filename.
An empty row key represents the album itself.

:author: William Boyles
"""

from azure.core.exceptions import ResourceNotFoundError, ResourceExistsError
from azure.identity import DefaultAzureCredential
from datetime import datetime, timezone
from flask import Blueprint, Response, current_app, url_for, redirect
from typing import Any

from ..lib.storage_helper import TableClient, get_table_client
from ..lib.models.media import MediaRecord, MediaType, PhotoRecord, VideoRecord, media_type_from_file_extension

api_albums_controller = Blueprint(
    "api_albums_controller",
    __name__,
    template_folder="templates",
    static_folder="static",
    url_prefix="/api/albums",
)

DEFAULT_ALBUM_THUMBNAIL: str = "/static/photo_album-512.webp"


@api_albums_controller.route("/<album_name>", methods=["POST"])
def create_album(album_name: str) -> Response | dict[str, Any]:
    """
    Create a new album.

    :param album_name: The name of the album to create. Must be unique.
    """

    account_name: str = current_app.config["account_name"]
    table_name: str = current_app.config["albums_table_name"]
    credential: DefaultAzureCredential = current_app.config["credential"]
    table_client: TableClient = get_table_client(account_name, table_name, credential)

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

    account_name: str = current_app.config["account_name"]
    table_name: str = current_app.config["albums_table_name"]
    credential: DefaultAzureCredential = current_app.config["credential"]
    table_client: TableClient = get_table_client(account_name, table_name, credential)

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

    account_name: str = current_app.config["account_name"]
    table_name: str = current_app.config["albums_table_name"]
    credential: DefaultAzureCredential = current_app.config["credential"]
    table_client: TableClient = get_table_client(account_name, table_name, credential)

    query = "PartitionKey eq @album_name"
    parameters = {"album_name": album_name}
    entities = table_client.query_entities(query_filter=query, parameters=parameters)
    for entity in entities:
        photo_copy = {
            "PartitionKey": new_name,
            "RowKey": entity["RowKey"],
            "Created": entity["Created"],
        }
        _ = table_client.create_entity(photo_copy)
        table_client.delete_entity(entity["PartitionKey"], entity["RowKey"])

    return Response(status=204)


@api_albums_controller.route("<album_name>", methods=["DELETE"])
def delete_album(album_name: str):
    """
    Delete an album.
    This does not delete the photos in the album.

    :param album_name: The name of the album to delete.
    """

    account_name: str = current_app.config["account_name"]
    table_name: str = current_app.config["albums_table_name"]
    credential: DefaultAzureCredential = current_app.config["credential"]
    table_client: TableClient = get_table_client(account_name, table_name, credential)

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
    Add a file to an album.

    :param album_name: The name of the album to add the file to.
    :param filename: The filename to add to the album.
    """

    account_name: str = current_app.config["account_name"]
    table_name: str = current_app.config["albums_table_name"]
    credential: DefaultAzureCredential = current_app.config["credential"]
    table_client: TableClient = get_table_client(account_name, table_name, credential)

    try:
        table_client.get_entity(partition_key=album_name, row_key="")
    except ResourceNotFoundError:
        return Response("Album does not exist", status=404)

    new_file = {
        "PartitionKey": album_name,
        "RowKey": filename,
        "Created": datetime.now(timezone.utc),
    }
    return table_client.create_entity(new_file)  # type: ignore


@api_albums_controller.route("<album_name>", methods=["GET"])
def list_album(album_name: str) -> Response | list[MediaRecord]:
    """
    List the files in an album, sorted by last modified time.

    :param album_name: The name of the album to list files for.
    """

    account_name: str = current_app.config["account_name"]
    table_name: str = current_app.config["albums_table_name"]
    credential: DefaultAzureCredential = current_app.config["credential"]
    table_client: TableClient = get_table_client(account_name, table_name, credential)

    query = "PartitionKey eq @album_name"
    parameters = {"album_name": album_name}
    query_results = table_client.query_entities(
        query_filter=query, parameters=parameters
    )
    album_exists = False
    medias = list[MediaRecord]()
    for entity in query_results:
        album_exists = True

        filename = entity["RowKey"]
        if len(filename) == 0:
            continue

        media_type = media_type_from_file_extension(filename)
        last_modified = entity["Created"]
        if media_type == MediaType.PHOTO:
            media_record = PhotoRecord(last_modified, filename)
        elif media_type == MediaType.VIDEO:
            media_record = VideoRecord(last_modified, filename)
        else: # unknown media type
            continue

        medias.append(media_record)

    if not album_exists:
        return Response("Album does not exist", status=404)
    
    return medias


@api_albums_controller.route("<album_name>/<filename>", methods=["DELETE"])
def remove_from_album(album_name: str, filename: str) -> Response:
    """
    Remove a photo from an album.
    This does not remove the photo itself or remove it from other albums.

    :param album_name: The name of the album to remove the photo from.
    :param filename: The filename of the photo to remove from the album.
    """

    account_name: str = current_app.config["account_name"]
    table_name: str = current_app.config["albums_table_name"]
    credential: DefaultAzureCredential = current_app.config["credential"]
    table_client: TableClient = get_table_client(account_name, table_name, credential)

    table_client.delete_entity(partition_key=album_name, row_key=filename)
    return Response(status=204)


@api_albums_controller.route("thumbnail/<album_name>", methods=["GET"])
def get_album_thumbnail(album_name: str) -> Response:
    """
    Get the thumbnail for an album.

    :param album_name: The name of the album to get the thumbnail for.
    """

    account_name: str = current_app.config["account_name"]
    table_name: str = current_app.config["albums_table_name"]
    credential: DefaultAzureCredential = current_app.config["credential"]
    table_client: TableClient = get_table_client(account_name, table_name, credential)
    
    query = "PartitionKey eq @album_name and RowKey ne ''"
    parameters = {
        "album_name": album_name
    }
    query_results = table_client.query_entities(
        query_filter=query,
        parameters=parameters,
        results_per_page=1
    )

    if (result := next(query_results, None)) is None:
        return redirect(DEFAULT_ALBUM_THUMBNAIL)  # type: ignore

    thumbnail_filename = result['RowKey']
    # TODO: Instead if redirecting back to ourselves, should we invoke thumbnail directly?
    response = redirect(
        url_for("crud_controller.thumbnail", filename=thumbnail_filename)
    )
    response.headers["Cache-Control"] = "public, max-age=900"

    return response # type: ignore


def remove_from_all_albums(filename: str) -> None:
    """
    Remove an entry from all albums.
    Most likely used when deleting an entry.

    :param filename: The filename of the entry to remove.
    """

    account_name: str = current_app.config["account_name"]
    table_name: str = current_app.config["albums_table_name"]
    credential: DefaultAzureCredential = current_app.config["credential"]
    table_client: TableClient = get_table_client(account_name, table_name, credential)

    query = "RowKey eq @filename"
    parameters = {"filename": filename}
    entities = table_client.query_entities(query_filter=query, parameters=parameters)
    for entity in entities:
        table_client.delete_entity(entity)


def all_album_file_names() -> list[str]:
    """
    List all photo names in all albums.
    Note that photos in multiple albums will be listed multiple times.
    """

    account_name: str = current_app.config["account_name"]
    table_name: str = current_app.config["albums_table_name"]
    credential: DefaultAzureCredential = current_app.config["credential"]
    table_client: TableClient = get_table_client(account_name, table_name, credential)

    entities = table_client.query_entities(query_filter="RowKey ne ''")
    return [row["RowKey"] for row in entities]
