"""
API endpoints for managing health

:author: William Boyles
"""

from flask import Blueprint, Response, current_app
from azure.identity import DefaultAzureCredential
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

    credential: DefaultAzureCredential = current_app.config["credential"]
    account_name = current_app.config["account_name"]
    blob_account_url: str = f"https://{account_name}.blob.core.windows.net"

    try:
        with BlobServiceClient(blob_account_url, credential, retry_policy=LinearRetry(retry_total=0)) as blob_client:
            _ = blob_client.list_containers(results_per_page=1).next().name
        return Response("ok", status=200, content_type="text/plain")
    except Exception as e:
        return Response(str(e), status=503, content_type="text/plain")
