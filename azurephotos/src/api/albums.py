"""
API endpoints for managing albums.

Albums are stored in Azure Table Storage.
The partition key is the album name, and the row key is the photo filename.
An empty row key represents the album itself.

:author: William Boyles
"""

from datetime import datetime, timezone
from azure.identity.aio import DefaultAzureCredential
from azure.core.exceptions import ResourceNotFoundError, ResourceExistsError
from azure.data.tables.aio import TableServiceClient, TableClient
from flask import Blueprint, Response, current_app, url_for, redirect

api_albums_controller = Blueprint(
    "api_albums_controller",
    __name__,
    template_folder="templates",
    static_folder="static",
    url_prefix="/api/albums",
)


def get_table_client() -> TableClient:
    """
    Built a TableClient for the albums table.

    flask.current_app.config must contain the following keys:
    - table_account_url: The URL of the Azure Table Storage account.
    - credential: The Azure credential to use for authentication.
    - albums_table_name: The name of the table to use for albums.
    """

    table_account_url: str = current_app.config["table_account_url"]
    credential: DefaultAzureCredential = current_app.config["credential"]
    albums_table_name: str = current_app.config["albums_table_name"]

    table_service_client = TableServiceClient(
        endpoint=table_account_url, credential=credential
    )
    table_client = table_service_client.get_table_client(albums_table_name)

    return table_client


@api_albums_controller.route("/<album_name>", methods=["POST"])
async def create_album(album_name: str) -> Response | dict[str,]:
    """
    Create a new album.

    :param album_name: The name of the album to create. Must be unique.
    """

    table_client = get_table_client()

    new_album = {
        "PartitionKey": album_name,
        "RowKey": "",
        "Created": datetime.now(timezone.utc),
    }

    try:
        return await table_client.create_entity(new_album)
    except ResourceExistsError:
        return Response("Album already exists", status=409)


@api_albums_controller.route("/albums", methods=["GET"])
async def list_albums() -> list[str]:
    """
    List all album names.
    """

    table_client = get_table_client()

    entities = table_client.query_entities(query_filter="RowKey eq ''")
    return [row["PartitionKey"] async for row in entities]


@api_albums_controller.route("<album_name>", methods=["DELETE"])
async def delete_album(album_name: str):
    """
    Delete an album.
    This does not delete the photos in the album.

    :param album_name: The name of the album to delete.
    """

    table_client = get_table_client()

    query = "PartitionKey eq @album_name"
    parameters = {"album_name": album_name}
    entities = table_client.query_entities(query_filter=query, parameters=parameters)
    async for entity in entities:
        await table_client.delete_entity(entity["PartitionKey"], entity["RowKey"])

    # TODO: Check if the album was actually deleted
    return Response(status=204)


@api_albums_controller.route("<album_name>/<filename>", methods=["POST"])
async def add_to_album(album_name: str, filename: str) -> Response | dict[str,]:
    """
    Add a photo to an album.

    :param album_name: The name of the album to add the photo to.
    :param filename: The filename of the photo to add to the album.
    """

    table_client = get_table_client()

    try:
        table_client.get_entity(partition_key=album_name, row_key="")
    except ResourceNotFoundError:
        return Response("Album does not exist", status=404)

    new_photo = {
        "PartitionKey": album_name,
        "RowKey": filename,
        "Created": datetime.now(timezone.utc),
    }
    return await table_client.create_entity(new_photo)


@api_albums_controller.route("<album_name>", methods=["GET"])
async def list_album(album_name: str) -> Response | list[str]:
    """
    List the photos in an album.

    :param album_name: The name of the album to list photos for.
    """

    table_client = get_table_client()

    query = "PartitionKey eq @album_name"
    parameters = {"album_name": album_name}
    entities = [
        entity
        async for entity in table_client.query_entities(
            query_filter=query, parameters=parameters
        )
    ]
    if len(entities) == 0:
        return Response("Album does not exist", status=404)

    return [entity["RowKey"] for entity in entities if entity["RowKey"] != ""]


@api_albums_controller.route("<album_name>/<filename>", methods=["DELETE"])
async def remove_from_album(album_name: str, filename: str) -> Response:
    """
    Remove a photo from an album.
    This does not remove the photo itself or remove it from other albums.

    :param album_name: The name of the album to remove the photo from.
    :param filename: The filename of the photo to remove from the album.
    """

    table_client = get_table_client()

    await table_client.delete_entity(partition_key=album_name, row_key=filename)
    return Response(status=204)


@api_albums_controller.route("thumbnail/<album_name>", methods=["GET"])
async def get_album_thumbnail(album_name: str) -> Response:
    """
    Get the thumbnail for an album.

    :param album_name: The name of the album to get the thumbnail for.
    """

    # Select a random photo from the album to use as the thumbnail
    album_photos = await list_album(album_name)
    print(album_photos)
    if isinstance(album_photos, Response) and album_photos.status_code == 404:
        return album_photos
    elif not isinstance(album_photos, list):
        return Response("Internal server error", status=500)
    elif len(album_photos) == 0:
        print("Trying to serve static photo_album-512.webp")
        return redirect("/static/photo_album-512.webp")

    thumbnail_filename = album_photos[0]
    return redirect(url_for("api_photos_controller.thumbnail", filename=thumbnail_filename))


async def remove_from_all_albums(filename: str) -> None:
    """
    Remove a photo from all albums.
    Most likely used when deleting a photo.

    :param filename: The filename of the photo to remove.
    """

    table_client = get_table_client()

    query = "RowKey eq @filename"
    parameters = {"filename": filename}
    entities = table_client.query_entities(query_filter=query, parameters=parameters)
    async for entity in entities:
        await table_client.delete_entity(entity)
