from .photos import api_photos_controller as photos_controller
from .albums import api_albums_controller as albums_controller
from .health import api_health_controller as health_controller

blueprints = {
    photos_controller,
    albums_controller,
    health_controller,
}
BASE_URL = None
