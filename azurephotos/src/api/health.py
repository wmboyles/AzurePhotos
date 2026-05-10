"""
API endpoints for managing health

:author: William Boyles
"""

from flask import Blueprint, Response, current_app
from azure.data.tables import TableClient
from azure.storage.blob import ContainerClient

api_health_controller = Blueprint(
    "api_health_controller",
    __name__,
    template_folder="templates",
    static_folder="static",
    url_prefix="/api/health",
)


@api_health_controller.route("/", methods=["GET"])
def health() -> Response:
    """
    If the app is running fine and can talk to storage, respond with HTTP 200.
    """

    container_clients: list[ContainerClient] = [current_app.config[k] for k in [
        "photos_container_client",
        "videos_container_client",
        "thumbnails_container_client"
    ]]
    table_clients: list[TableClient] = [current_app.config[k] for k in [
        "albums_table_client"
    ]]

    try:
        for container_client in container_clients:
            _ = container_client.get_container_properties(timeout=5)
        for table_client in table_clients:
            _ = next(table_client.list_entities(results_per_page=1), None)
        
        return Response("ok", status=200, content_type="text/plain")
    except Exception as e:
        return Response(str(e), status=503, content_type="text/plain")
