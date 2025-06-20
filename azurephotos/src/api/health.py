"""
API endpoints for managing health

:author: William Boyles
"""

from flask import Blueprint, Response

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
    If the app is running fine, respond with HTTP 200.
    """
    
    # TODO: check access to storage
    return Response(status=200)
