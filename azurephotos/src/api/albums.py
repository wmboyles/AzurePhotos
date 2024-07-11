from datetime import datetime, timezone

from azure.identity.aio import DefaultAzureCredential
from azure.core.exceptions import ResourceNotFoundError, ResourceExistsError
from azure.data.tables.aio import TableServiceClient
from flask import Blueprint, Response, current_app

api_albums_controller = Blueprint(
    "api_albums_controller",
    __name__,
    template_folder="templates",
    static_folder="static",
    url_prefix="/",
)

albums_table_name = "Albums"


@api_albums_controller.route("/albums/<album_name>", methods=["POST"])
async def create_album(album_name: str):
    table_account_url: str = current_app.config["table_account_url"]
    credential: DefaultAzureCredential = current_app.config["credential"]

    new_album = {
        "PartitionKey": album_name,
        "RowKey": "",
        "Created": datetime.now(timezone.utc),
    }

    table_service_client = TableServiceClient(
        endpoint=table_account_url, credential=credential
    )
    table_client = table_service_client.get_table_client(albums_table_name)
    try:
        return await table_client.create_entity(new_album)
    except ResourceExistsError:
        return Response("Album already exists", status=409)


@api_albums_controller.route("/albums", methods=["GET"])
async def list_albums():
    table_account_url: str = current_app.config["table_account_url"]
    credential: DefaultAzureCredential = current_app.config["credential"]

    table_service_client = TableServiceClient(
        endpoint=table_account_url, credential=credential
    )
    table_client = table_service_client.get_table_client(albums_table_name)
    entities = table_client.query_entities(query_filter="RowKey eq ''")
    return [row["PartitionKey"] async for row in entities]


@api_albums_controller.route("/albums/<album_name>", methods=["DELETE"])
async def delete_album(album_name: str):
    table_account_url: str = current_app.config["table_account_url"]
    credential: DefaultAzureCredential = current_app.config["credential"]

    table_service_client = TableServiceClient(
        endpoint=table_account_url, credential=credential
    )
    table_client = table_service_client.get_table_client(albums_table_name)

    query = "PartitionKey eq @album_name"
    parameters = {"album_name": album_name}
    entities = table_client.query_entities(query_filter=query, parameters=parameters)
    async for entity in entities:
        await table_client.delete_entity(entity["RowKey"], entity["PartitionKey"])

    return Response(status=204)


@api_albums_controller.route("/albums/<album_name>/<filename>", methods=["POST"])
async def add_to_album(album_name: str, filename: str):
    table_account_url: str = current_app.config["table_account_url"]
    credential: DefaultAzureCredential = current_app.config["credential"]

    table_service_client = TableServiceClient(
        endpoint=table_account_url, credential=credential
    )
    table_client = table_service_client.get_table_client(albums_table_name)

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


@api_albums_controller.route("/albums/<album_name>", methods=["GET"])
async def list_album(album_name: str):
    table_account_url: str = current_app.config["table_account_url"]
    credential: DefaultAzureCredential = current_app.config["credential"]

    table_service_client = TableServiceClient(
        endpoint=table_account_url, credential=credential
    )
    table_client = table_service_client.get_table_client(albums_table_name)

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

    return [entity["RowKey"] for entity in entities]


@api_albums_controller.route("/albums/<album_name>/<filename>", methods=["DELETE"])
async def remove_from_album(album_name: str, filename: str):
    table_account_url: str = current_app.config["table_account_url"]
    credential: DefaultAzureCredential = current_app.config["credential"]

    table_service_client = TableServiceClient(
        endpoint=table_account_url, credential=credential
    )
    table_client = table_service_client.get_table_client(albums_table_name)

    await table_client.delete_entity(partition_key=album_name, row_key=filename)
    return Response(status=204)


async def remove_from_all_albums(filename: str):
    table_account_url: str = current_app.config["table_account_url"]
    credential: DefaultAzureCredential = current_app.config["credential"]
    
    table_service_client = TableServiceClient(
        endpoint=table_account_url, credential=credential
    )
    table_client = table_service_client.get_table_client(albums_table_name)

    query = "RowKey eq @filename"
    parameters = {"filename": filename}
    entities = table_client.query_entities(query_filter=query, parameters=parameters)
    async for entity in entities:
        await table_client.delete_entity(entity)
