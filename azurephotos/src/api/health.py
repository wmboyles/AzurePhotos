"""
API endpoints for managing health

:author: William Boyles
"""

from flask import Blueprint, Response, current_app
from azure.storage.blob import BlobServiceClient, LinearRetry

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

    blob_service_client: BlobServiceClient = current_app.config["blob_service_client"]

    try:
        blob_service_client.get_account_information(retry_policy=LinearRetry(retry_total=0))
        return Response("ok", status=200, content_type="text/plain")
    except Exception as e:
        return Response(str(e), status=503, content_type="text/plain")
