from flask import Blueprint, render_template, current_app
import asyncio
from azure.storage.blob.aio import ContainerClient
from azure.identity.aio import DefaultAzureCredential

from ..api.albums import list_albums

landing_view_controller = Blueprint(
    "landing_view_controller",
    __name__,
    template_folder="templates",
    static_folder="static",
    url_prefix="/",
)

async def get_image_names(blob_account_url: str, container_name: str, credential: DefaultAzureCredential):
    container_client = ContainerClient(blob_account_url, container_name, credential)
    return [name async for name in container_client.list_blob_names()]

@landing_view_controller.route("/")
def index():
    blob_account_url: str = current_app.config["blob_account_url"]
    photos_container_name: str = current_app.config["photos_container_name"]
    credential: DefaultAzureCredential = current_app.config["credential"]

    image_names = asyncio.run(get_image_names(blob_account_url, photos_container_name, credential))
    album_names = asyncio.run(list_albums())
    return render_template("index.html", images=image_names, albums=album_names)


blueprints = {landing_view_controller}