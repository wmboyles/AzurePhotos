import asyncio
from datetime import datetime, timedelta

from azure.identity.aio import DefaultAzureCredential
from azure.storage.blob import ContainerSasPermissions, generate_container_sas
from azure.storage.blob.aio import BlobServiceClient, ContainerClient
from flask import Flask, redirect, render_template

loop = asyncio.get_event_loop()
app = Flask(__name__)
credential = DefaultAzureCredential()

account_name = "wboylesbackups"
account_url = f"https://{account_name}.blob.core.windows.net"
container_name = "thumbnails"

container_sas = None
container_sas_expiry = None


async def get_container_sas():
    global container_sas, container_sas_expiry

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
    container_sas_expiry = sas_end


async def get_image_names():
    container_client = ContainerClient(account_url, container_name, credential)  # type: ignore
    return [name async for name in container_client.list_blob_names()]


@app.route("/thumbnail/<filename>", methods=["GET"])
def thumbnail(filename: str):
    return redirect(f"{account_url}/{container_name}/{filename}?{container_sas}")


@app.route("/")
def index():
    loop.run_until_complete(get_container_sas())
    image_names = loop.run_until_complete(get_image_names())
    return render_template("index.html", images=image_names)


if __name__ == "__main__":
    app.run()
