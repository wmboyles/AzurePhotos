from .photos import api_photos_controller as photos_controller
from .albums import api_albums_controller as albums_controller


blueprints = {
    photos_controller,
    albums_controller,
}
BASE_URL = None
