import asyncio
from datetime import datetime, timedelta

from azure.core.exceptions import ResourceNotFoundError
from azure.identity.aio import DefaultAzureCredential
from azure.storage.blob import ContainerSasPermissions, generate_container_sas
from azure.storage.blob.aio import BlobServiceClient, ContainerClient
from azure.data.tables.aio import TableServiceClient
from flask import Flask, Response, redirect, render_template, request
from werkzeug.utils import secure_filename

loop = asyncio.get_event_loop()
app = Flask(__name__)
credential = DefaultAzureCredential()

account_name = "wboylesbackups"
blob_account_url = f"https://{account_name}.blob.core.windows.net"
table_account_url = f"https://{account_name}.table.core.windows.net"
thumbnails_container_name = "thumbnails"
photos_container_name = "photos"

thumbnails_container_sas = None
photos_container_sas = None


MAX_ALBUM_NAME_BYTES = 31

# TODO: We could probably change from hex to a longer alphabet to allow longer names. [0-9a-zA-Z] is the best, allowing 42 bytes of input
def encode_album_name(album_name: str) -> str:
    album_name_utf8 = album_name.encode("utf-8")
    if len(album_name_utf8) > MAX_ALBUM_NAME_BYTES:
        raise ValueError("album_name is too long")
    
    return f"A{album_name_utf8.hex()}"

def decode_album_name(encoded_album_name: str) -> str:
    return bytes.fromhex(encoded_album_name[1:]).decode("utf-8")


async def get_container_sas(container_name: str):
    sas_start = datetime.utcnow() - timedelta(minutes=1)
    sas_end = datetime.utcnow() + timedelta(minutes=30)

    bsc = BlobServiceClient(blob_account_url, credential)  # type: ignore

    user_delegation_key = await bsc.get_user_delegation_key(
        key_start_time=sas_start,
        key_expiry_time=sas_end,
    )

    container_sas = generate_container_sas(
        account_name=account_name,
        container_name=container_name,
        user_delegation_key=user_delegation_key,
        permission=ContainerSasPermissions(read=True),
        start=sas_start,
        expiry=sas_end,
    )

    return container_sas


async def get_image_names(container_name: str):
    container_client = ContainerClient(blob_account_url, container_name, credential)  # type: ignore
    return [name async for name in container_client.list_blob_names()]


@app.route("/thumbnail/<filename>", methods=["GET"])
async def thumbnail(filename: str):
    return redirect(f"{blob_account_url}/{thumbnails_container_name}/{filename}?{thumbnails_container_sas}")


@app.route("/fullsize/<filename>", methods=["GET"])
async def fullsize(filename: str):
    return redirect(f"{blob_account_url}/{photos_container_name}/{filename}?{photos_container_sas}")


@app.route("/albums", methods=["GET"])
async def list_albums():
    table_service_client = TableServiceClient(endpoint=table_account_url, credential=credential)
    async with table_service_client:
        tables_list = table_service_client.list_tables()
        return [decode_album_name(table.name) async for table in tables_list]

@app.route("/albums/<album_name>", methods=["POST"])
async def create_album(album_name: str):
    table_service_client = TableServiceClient(endpoint=table_account_url, credential=credential)
    async with table_service_client:
        encoded_album_name = encode_album_name(album_name)
        print(f"Creating table `{encoded_album_name}`", type(encoded_album_name))
        await table_service_client.create_table(encoded_album_name)
        return Response(status=201)

@app.route("/delete/<filename>", methods=["DELETE"])
async def delete(filename: str):
    try:
        thumbnail_container_client = ContainerClient(blob_account_url, thumbnails_container_name, credential) # type: ignore
        async with thumbnail_container_client:
            await thumbnail_container_client.delete_blob(filename)

        photos_container_client = ContainerClient(blob_account_url, photos_container_name, credential) # type: ignore
        async with photos_container_client:
            await photos_container_client.delete_blob(filename)
    except ResourceNotFoundError as e:
        return Response(e.message, status=404)

    # Client JS code should remove image from view
    return Response(status=200)


@app.route("/upload", methods=["POST"])
async def upload():
    container_client = ContainerClient(blob_account_url, photos_container_name, credential) # type: ignore
    async with container_client:
        files = request.files.getlist("upload")
        for file in files:
            save_filename = secure_filename(str(file.filename))
            await container_client.upload_blob(save_filename, file.stream)

    # TODO: Allow uploading photos with refreshing the page
    return redirect("/")


@app.route("/")
def index():
    global thumbnails_container_sas, photos_container_sas
    thumbnails_container_sas = loop.run_until_complete(
        get_container_sas(thumbnails_container_name)
    )
    photos_container_sas = loop.run_until_complete(
        get_container_sas(photos_container_name)
    )

    image_names = loop.run_until_complete(get_image_names(photos_container_name))

    return render_template("index.html", images=image_names)


if __name__ == "__main__":
    app.run()
