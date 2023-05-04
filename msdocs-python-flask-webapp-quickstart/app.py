from datetime import datetime, timedelta
import asyncio

from azure.identity.aio import DefaultAzureCredential
from azure.storage.blob import ContainerSasPermissions, generate_container_sas
from azure.storage.blob.aio import BlobServiceClient, ContainerClient
from flask import Flask, redirect, render_template, request

app = Flask(__name__)
credential = DefaultAzureCredential()

account_name = "wboylesbackups"
account_url = f"https://{account_name}.blob.core.windows.net"
container_name = "photos"
container_sas = None
container_client = ContainerClient(account_url, container_name, credential)
bsc = BlobServiceClient(account_url, credential)
image_names = []


async def get_container_sas():
    print("Getting container sas")

    sas_start = datetime.utcnow() - timedelta(minutes=1)
    sas_end = datetime.utcnow() + timedelta(minutes=10)

    user_delegation_key = await bsc.get_user_delegation_key(
        key_start_time=sas_start,
        key_expiry_time=sas_end,
    )

    global container_sas
    container_sas = generate_container_sas(
        account_name=account_name,
        container_name=container_name,
        user_delegation_key=user_delegation_key,
        permission=ContainerSasPermissions(read=True),
        start=sas_start,
        expiry=sas_end,
    )


async def get_image_names():
    print("Getting image names")
    global image_names
    async for name in container_client.list_blob_names():
        image_names.append(name)


@app.route("/thumbnail/<filename>", methods=["GET"])
async def thumbnail(filename: str):
    blob_url = container_client.get_blob_client(filename).url
    return redirect(f"{blob_url}?{container_sas}")


@app.route("/")
async def index():
    return render_template("index.html", images=image_names)


asyncio.run(get_container_sas())
asyncio.run(get_image_names())

if __name__ == '__main__':    
    app.run()
