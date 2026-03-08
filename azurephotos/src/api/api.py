from .crud_controller import crud_controller
from .albums import api_albums_controller as albums_controller
from .health import api_health_controller as health_controller

blueprints = {
    crud_controller,
    albums_controller,
    health_controller,
}
BASE_URL = None
