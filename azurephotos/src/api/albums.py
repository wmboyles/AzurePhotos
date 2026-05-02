"""
API endpoints for managing albums.

Albums are stored in Azure Table Storage.
The partition key is the album name, and the row key is the photo filename.
An empty row key represents the album itself.

:author: William Boyles
"""

from azure.core.exceptions import ResourceNotFoundError, ResourceExistsError
from azure.identity import DefaultAzureCredential
from datetime import datetime, timezone, timedelta
from flask import Blueprint, Response, current_app, url_for, redirect
from typing import Any

from .media_cache import invalidates_media_cache
from ..lib.storage_helper import TableClient, get_table_client
from ..lib.refresher import refreshed
from ..lib.models.media import MediaRecord, MediaType, PhotoRecord, VideoRecord, media_type_from_file_extension

api_albums_controller = Blueprint(
    "api_albums_controller",
    __name__,
    template_folder="templates",
    static_folder="static",
    url_prefix="/api/albums",
)

DEFAULT_ALBUM_THUMBNAIL: str = "/static/photo_album-512.webp"
NONE_ALBUM_NAME = "__NONE__"


@api_albums_controller.route("/<album_name>", methods=["POST"])
def create_album(album_name: str) -> Response | dict[str, Any]:
    """
    Create a new album.

    :param album_name: The name of the album to create. Must be unique.
    """

    if album_name == NONE_ALBUM_NAME:
        return Response(f"Album name {NONE_ALBUM_NAME} is reserved", status=403)

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
    
    return _list_albums(account_name, table_name, credential)


@refreshed(every=timedelta(seconds=30))
def _list_albums(account_name: str, table_name: str, credential: DefaultAzureCredential) -> list[str]:
    """
    List all album names.
    """
    
    print("LISTING ALBUMS")

    table_client: TableClient = get_table_client(account_name, table_name, credential)

    query = "PartitionKey ne @reserved_album_name and RowKey eq ''"
    parameters = {"reserved_album_name": NONE_ALBUM_NAME}
    entities = table_client.query_entities(query_filter=query, parameters=parameters)
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

    if album_name == NONE_ALBUM_NAME:
        return Response(f"Album '{NONE_ALBUM_NAME}' is reserved and cannot be renamed", status=403)

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
@invalidates_media_cache
def delete_album(album_name: str) -> Response:
    """
    Delete an album.
    This does not delete the photos in the album.

    :param album_name: The name of the album to delete.
    """

    print(f"RECEIVED ALBUM NAME {album_name}")

    if album_name == NONE_ALBUM_NAME:
        return Response(f"Album name '{NONE_ALBUM_NAME}' is reserved and cannot be deleted", status=403)

    account_name: str = current_app.config["account_name"]
    table_name: str = current_app.config["albums_table_name"]
    credential: DefaultAzureCredential = current_app.config["credential"]
    table_client: TableClient = get_table_client(account_name, table_name, credential)

    query = "PartitionKey eq @album_name"
    parameters = {"album_name": album_name}
    entities = table_client.query_entities(query_filter=query, parameters=parameters)
    entity = None
    for entity in entities:
        partition_key = entity["PartitionKey"]
        row_key = entity["RowKey"]
        if row_key: 
            new_entity = dict(entity)
            new_entity["PartitionKey"] = NONE_ALBUM_NAME
            _ = table_client.create_entity(new_entity) 
        
        table_client.delete_entity(partition_key, row_key)

    if not entity: # No results. Loop didn't run
        return Response(f"Album '{album_name}' not found", status=404)

    return Response(status=204)


@api_albums_controller.route("<album_name>/<filename>", methods=["POST"])
@invalidates_media_cache
def add_to_album(album_name: str, filename: str) -> Response:
    """
    Add a file to an album.

    :param album_name: The name of the album to add the file to.
    :param filename: The filename to add to the album.
    """

    if album_name == NONE_ALBUM_NAME:
        return Response(f"Album name '{NONE_ALBUM_NAME}' is reserved and cannot be added to directly")

    account_name: str = current_app.config["account_name"]
    table_name: str = current_app.config["albums_table_name"]
    credential: DefaultAzureCredential = current_app.config["credential"]
    table_client: TableClient = get_table_client(account_name, table_name, credential)

    try:
        non_album_entity = table_client.get_entity(partition_key=NONE_ALBUM_NAME, row_key=filename)
    except ResourceNotFoundError:
        return Response(f"Filename '{filename}' does not exist or is already in an album", status=404)
    
    try:
        _ = table_client.get_entity(partition_key=album_name, row_key="")
    except ResourceNotFoundError:
        return Response(f"Album '{album_name}' does not exist", status=404)

    # Add new entity to album
    new_file = dict(non_album_entity)
    new_file["PartitionKey"] = album_name
    _ = table_client.create_entity(new_file) 

    # Delete existing entity
    _ = table_client.delete_entity(partition_key=NONE_ALBUM_NAME, row_key=filename)

    return Response(status=201)

@invalidates_media_cache
def _add_to_reserved_album(filename: str, date_taken: datetime) -> Response:
    """
    Add a photo to the "none album" album.
    Should only be used when first uploading a photo.
    """
    
    account_name: str = current_app.config["account_name"]
    table_name: str = current_app.config["albums_table_name"]
    credential: DefaultAzureCredential = current_app.config["credential"]
    table_client: TableClient = get_table_client(account_name, table_name, credential)

    new_file = {
        "PartitionKey": NONE_ALBUM_NAME,
        "RowKey": filename,
        "Created": date_taken
    }
    _ = table_client.create_entity(new_file)
    
    return Response(status=201)


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
    
    return sorted(
        medias,
        key=lambda m: m.last_modified,
        reverse=True
    )


@api_albums_controller.route("<album_name>/<filename>", methods=["DELETE"])
@invalidates_media_cache
def remove_from_album(album_name: str, filename: str) -> Response:
    """
    Remove a photo from an album.
    This does not remove the photo itself or remove it from other albums.

    :param album_name: The name of the album to remove the photo from.
    :param filename: The filename of the photo to remove from the album.
    """

    if album_name == NONE_ALBUM_NAME:
        return Response(f"Album name '{NONE_ALBUM_NAME}' is reserved and cannot be deleted from")

    account_name: str = current_app.config["account_name"]
    table_name: str = current_app.config["albums_table_name"]
    credential: DefaultAzureCredential = current_app.config["credential"]
    table_client: TableClient = get_table_client(account_name, table_name, credential)

    # Get existing entity
    existing_entity = table_client.get_entity(partition_key=album_name, row_key=filename)
    
    # Add new entity to NONE album
    new_entity = dict(existing_entity)
    new_entity["PartitionKey"] = NONE_ALBUM_NAME
    _ = table_client.create_entity(new_entity)

    # Delete old entity
    _ = table_client.delete_entity(partition_key=album_name, row_key=filename)
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


@invalidates_media_cache
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


@refreshed(every=timedelta(seconds=30))
def non_album_file_names(account_name: str, table_name: str, credential: DefaultAzureCredential) -> list[MediaRecord]:
    """
    Get all entities not in an album
    """
    
    table_client: TableClient = get_table_client(account_name, table_name, credential)

    query = "PartitionKey eq @reserved_album_name and RowKey ne ''"
    parameters = {"reserved_album_name": NONE_ALBUM_NAME}
    entities = table_client.query_entities(query_filter=query, parameters=parameters)

    results = list[MediaRecord]()
    for row in entities:
        filename = row["RowKey"]
        last_modified = row["Created"]

        match (media_type_from_file_extension(filename)):
            case MediaType.PHOTO:
                result = PhotoRecord(last_modified, filename)
            case MediaType.VIDEO:
                result = VideoRecord(last_modified, filename)
            case _:
                raise Exception(f"Unknown media type")
        
        results.append(result)

    return results
