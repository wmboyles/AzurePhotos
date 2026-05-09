"""
API endpoints for managing albums.

Albums are stored in Azure Table Storage.
The partition key is the album name, and the row key is the photo filename.
An empty row key represents the album itself.

:author: William Boyles
"""

from azure.core.exceptions import ResourceNotFoundError, ResourceExistsError
from azure.data.tables import TableClient
from datetime import datetime, timezone, timedelta
from flask import Blueprint, Response, current_app, url_for, redirect
from typing import Any

from .media_cache import invalidate_media_cache
from ..lib.refresher import refreshed
from ..lib.models.media import MediaRecord

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

    table_client = current_app.config["albums_table_client"]

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

    return _list_albums()


@refreshed(every=timedelta(seconds=30))
def _list_albums() -> list[str]:

    """
    List all album names.
    """

    table_client: TableClient = current_app.config["albums_table_client"]

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
        return Response(
            f"Album '{NONE_ALBUM_NAME}' is reserved and cannot be renamed", status=403
        )
    if new_name == NONE_ALBUM_NAME:
        return Response(
            f"Album name '{NONE_ALBUM_NAME}' is reserved and cannot be renamed to", status=403
        )

    table_client: TableClient = current_app.config["albums_table_client"]

    query = "PartitionKey eq @album_name"
    parameters = {"album_name": album_name}
    entities = table_client.query_entities(query_filter=query, parameters=parameters)
    entity = None
    for entity in entities:
        photo_copy = {
            "PartitionKey": new_name,
            "RowKey": entity["RowKey"],
            "Created": entity["Created"],
        }
        _ = table_client.create_entity(photo_copy)

        try:
            table_client.delete_entity(entity["PartitionKey"], entity["RowKey"])
        except ResourceNotFoundError:
            # Entry already deleted
            pass

    if not entity:  # No results. Loop didn't run
        return Response(f"Album '{album_name}' not found", status=404)

    return Response(status=204)


@api_albums_controller.route("/<album_name>", methods=["DELETE"])
def delete_album(album_name: str) -> Response:
    """
    Delete an album.
    Entries in the album will be moved to the "none" album.

    :param album_name: The name of the album to delete.
    """

    if album_name == NONE_ALBUM_NAME:
        return Response(
            f"Album name '{NONE_ALBUM_NAME}' is reserved and cannot be deleted",
            status=403,
        )

    table_client: TableClient = current_app.config["albums_table_client"]

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

        try:
            table_client.delete_entity(partition_key, row_key)
        except ResourceNotFoundError:
            # Entry already deleted
            pass

    if not entity:  # No results. Loop didn't run
        return Response(f"Album '{album_name}' not found", status=404)
    
    invalidate_media_cache()
    return Response(status=204)


@api_albums_controller.route("/<album_name>/<filename>", methods=["POST"])
def move_to_album(album_name: str, filename: str) -> Response:
    """
    Move an existing file from the "none" album to another album.
    For uploading a new file to an album, use :func:`delete_album`

    :param album_name: The name of the album to add the file to.
    :param filename: The filename to add to the album.
    """

    if album_name == NONE_ALBUM_NAME:
        return Response(
            f"Album name '{NONE_ALBUM_NAME}' is reserved and cannot be added to directly",
            status=403
        )

    table_client: TableClient = current_app.config["albums_table_client"]

    try:
        non_album_entity = table_client.get_entity(
            partition_key=NONE_ALBUM_NAME, row_key=filename
        )
    except ResourceNotFoundError:
        return Response(
            f"Filename '{filename}' does not exist or is already in an album",
            status=404,
        )

    try:
        _ = table_client.get_entity(partition_key=album_name, row_key="")
    except ResourceNotFoundError:
        return Response(f"Album '{album_name}' does not exist", status=404)

    # Add new entity to album
    new_file = dict(non_album_entity)
    new_file["PartitionKey"] = album_name
    _ = table_client.create_entity(new_file)

    # Delete existing entity
    try:
        _ = table_client.delete_entity(partition_key=NONE_ALBUM_NAME, row_key=filename)
    except ResourceNotFoundError:
        # Entry already deleted
        pass

    invalidate_media_cache()
    return Response(status=201)


# Don't invalidate media cache. Caller will decide if they want to do that.
def upload_to_album(filename: str, date_taken: datetime, album_name: str) -> Response:
    """
    Upload a photo directly to an album.
    For moving photos between albums, see :func:`move_to_album`.
    
    Prerequisites:
    - Album already exists
    - Photo does not exist in another album, including "none" album

    :param filename: The filename to add to the album
    :param date_taken: When the file was created
    :param album_name: Name of album to add to
    """

    table_client: TableClient = current_app.config["albums_table_client"]

    # Check that album exists
    # TODO: Could we cache this and avoid checking every time?
    try:
        # None album entry doesn't have an empty row key. We can assume it always exists
        if album_name != NONE_ALBUM_NAME:
            _ = table_client.get_entity(partition_key=album_name, row_key="")
    except ResourceNotFoundError:
        return Response(f"Album '{album_name}' does not exist", status=404)

    new_file = {
        "PartitionKey": album_name,
        "RowKey": filename,
        "Created": date_taken,
    }
    _ = table_client.create_entity(new_file)

    return Response(status=201)


@api_albums_controller.route("/<album_name>", methods=["GET"])
def list_album(album_name: str) -> Response | list[MediaRecord]:
    """
    List the files in an album, sorted by last modified time.

    :param album_name: The name of the album to list files for.
    """

    table_client: TableClient = current_app.config["albums_table_client"]

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

        last_modified = entity["Created"]
        media_record = MediaRecord.from_filename(last_modified, filename)

        if media_record:
            medias.append(media_record)

    if not album_exists:
        return Response("Album does not exist", status=404)

    return sorted(medias, reverse=True)


@api_albums_controller.route("/<album_name>/<filename>", methods=["DELETE"])
def remove_from_album(album_name: str, filename: str) -> Response:
    """
    Remove a photo from an album, putting it back in the "none" album.
    This does not remove the photo itself or remove it from other albums.

    :param album_name: The name of the album to remove the photo from.
    :param filename: The filename of the photo to remove from the album.
    """

    if album_name == NONE_ALBUM_NAME:
        return Response(
            f"Album name '{NONE_ALBUM_NAME}' is reserved and cannot be deleted from",
            status=403
        )

    table_client: TableClient = current_app.config["albums_table_client"]

    # Get existing entity
    try:
        existing_entity = table_client.get_entity(
            partition_key=album_name, row_key=filename
        )
    except ResourceNotFoundError:
        return Response(f"'{filename}' not found in album '{album_name}'", status=404)

    # Add new entity to NONE album
    new_entity = dict(existing_entity)
    new_entity["PartitionKey"] = NONE_ALBUM_NAME
    _ = table_client.create_entity(new_entity)

    # Delete old entity
    try:
        _ = table_client.delete_entity(partition_key=album_name, row_key=filename)
    except ResourceNotFoundError:
        # Entry already removed
        pass

    invalidate_media_cache()
    return Response(status=204)


@api_albums_controller.route("/thumbnail/<album_name>", methods=["GET"])
def get_album_thumbnail(album_name: str) -> Response:
    """
    Get the thumbnail for an album.

    :param album_name: The name of the album to get the thumbnail for.
    """

    table_client: TableClient = current_app.config["albums_table_client"]

    query = "PartitionKey eq @album_name and RowKey ne ''"
    parameters = {"album_name": album_name}
    query_results = table_client.query_entities(
        query_filter=query, parameters=parameters, results_per_page=1
    )

    if (result := next(query_results, None)) is None:
        return redirect(DEFAULT_ALBUM_THUMBNAIL)  # type: ignore

    thumbnail_filename = result["RowKey"]
    # TODO: Instead if redirecting back to ourselves, should we invoke thumbnail directly?
    response = redirect(
        url_for("crud_controller.thumbnail", filename=thumbnail_filename)
    )
    response.headers["Cache-Control"] = "public, max-age=900"

    return response  # type: ignore


# Don't invalidate media cache. Caller will decide if they want to do that.
def remove_from_all_albums(filename: str) -> set[str]:
    """
    Remove an entry from all albums.
    Most likely used when deleting an entry.

    :param filename: The filename of the entry to remove.
    :return: The set of albums that were affected by the removal.
    """

    table_client: TableClient = current_app.config["albums_table_client"]

    query = "RowKey eq @filename"
    parameters = {"filename": filename}
    entities = table_client.query_entities(query_filter=query, parameters=parameters)
    albums_affected = set[str]()
    for entity in entities:
        try:
            table_client.delete_entity(entity)
            albums_affected.add(entity["PartitionKey"])
        except ResourceNotFoundError:
            # Entry already deleted
            pass

    return albums_affected


@refreshed(every=timedelta(seconds=30))
def non_album_file_names() -> list[MediaRecord]:
    """
    Get all entities not in an album
    """

    table_client: TableClient = current_app.config["albums_table_client"]

    query = "PartitionKey eq @reserved_album_name and RowKey ne ''"
    parameters = {"reserved_album_name": NONE_ALBUM_NAME}
    entities = table_client.query_entities(query_filter=query, parameters=parameters)

    results = list[MediaRecord]()
    for row in entities:
        filename = row["RowKey"]
        last_modified = row["Created"]

        result = MediaRecord.from_filename(last_modified, filename)
        if result:
            results.append(result)

    return results
