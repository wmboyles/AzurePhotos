from flask import Blueprint, render_template, current_app
from asyncio import AbstractEventLoop
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
    event_loop: AbstractEventLoop = current_app.config["event_loop"]
    blob_account_url: str = current_app.config["blob_account_url"]
    photos_container_name: str = current_app.config["photos_container_name"]
    credential: DefaultAzureCredential = current_app.config["credential"]

    image_names = event_loop.run_until_complete(get_image_names(blob_account_url, photos_container_name, credential))
    album_names = event_loop.run_until_complete(list_albums())
    return render_template("index.html", images=image_names, albums=album_names)


blueprints = {landing_view_controller}