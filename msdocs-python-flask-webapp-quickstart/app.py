import asyncio
from datetime import datetime, timedelta

from azure.identity.aio import DefaultAzureCredential
from azure.storage.blob import ContainerSasPermissions, generate_container_sas
from azure.storage.blob.aio import BlobServiceClient, ContainerClient
from flask import Flask, redirect, render_template, Response

loop = asyncio.get_event_loop()
app = Flask(__name__)
credential = DefaultAzureCredential()

account_name = "wboylesbackups"
account_url = f"https://{account_name}.blob.core.windows.net"
thumbnails_container_name = "thumbnails"
photos_container_name = "photos"

thumbnails_container_sas = None
photos_container_sas = None

async def get_container_sas(container_name: str):
    sas_start = datetime.utcnow() - timedelta(minutes=1)
    sas_end = datetime.utcnow() + timedelta(minutes=30)

    bsc = BlobServiceClient(account_url, credential)  # type: ignore

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
    container_client = ContainerClient(account_url, container_name, credential)  # type: ignore
    return [name async for name in container_client.list_blob_names()]


@app.route("/thumbnail/<filename>", methods=["GET"])
def thumbnail(filename: str):
    return redirect(f"{account_url}/{thumbnails_container_name}/{filename}?{thumbnails_container_sas}")

@app.route("/fullsize/<filename>", methods=["GET"])
def fullsize(filename: str):
    return redirect(f"{account_url}/{photos_container_name}/{filename}?{photos_container_sas}")

@app.route("/delete/<filename>", methods=["DELETE"])
async def delete(filename: str):
    thumbnail_container_client = ContainerClient(account_url, thumbnails_container_name, credential)
    async with thumbnail_container_client:
        await thumbnail_container_client.delete_blob(filename)

    photos_container_client = ContainerClient(account_url, photos_container_name, credential)
    async with photos_container_client:
        await photos_container_client.delete_blob(filename)

    # Client JS code should remove image from view
    return Response(status=200)

@app.route("/")
def index():
    global thumbnails_container_sas, photos_container_sas
    thumbnails_container_sas = loop.run_until_complete(get_container_sas(thumbnails_container_name))
    photos_container_sas = loop.run_until_complete(get_container_sas(photos_container_name))
    
    image_names = loop.run_until_complete(get_image_names(photos_container_name))
    
    return render_template("index.html", images=image_names)


if __name__ == "__main__":
    app.run()
