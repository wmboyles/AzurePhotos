from concurrent.futures import ThreadPoolExecutor
from flask import Blueprint, render_template, Response, current_app
from flask.ctx import AppContext

from ..api.albums import list_albums, list_album
from ..api.media_cache import all_media

landing_view_controller = Blueprint(
    "landing_view_controller",
    __name__,
    template_folder="templates",
    static_folder="static",
    url_prefix="/",
)

albums_view_controller = Blueprint(
    "albums_view_controller",
    __name__,
    template_folder="templates",
    static_folder="static",
    url_prefix="/albums",
)

blueprints = {
    landing_view_controller,
    albums_view_controller,
}

@landing_view_controller.route("/", methods=["GET"])
def main() -> str:
    def all_media_threaded(app_context: AppContext):
        with app_context:
            return all_media()
        
    def list_albums_threaded(app_context: AppContext):
        with app_context:
            return list_albums()

    with ThreadPoolExecutor() as executor:
        all_media_future = executor.submit(all_media_threaded, current_app.app_context())
        list_albums_future = executor.submit(list_albums_threaded, current_app.app_context())
        
        media = all_media_future.result()
        album_names = list_albums_future.result()
    
    return render_template("photos.html", medias=media, albums=album_names)

@albums_view_controller.route("/<album_name>", methods=["GET"])
def album(album_name: str) -> str | Response:
    def list_album_threaded(app_context: AppContext):
        with app_context:
            return list_album(album_name)
    
    def list_albums_threaded(app_context: AppContext):
        with app_context:
            return list_albums()
        
    with ThreadPoolExecutor() as executor:
        files_in_album_future = executor.submit(list_album_threaded, current_app.app_context())
        list_albums_future = executor.submit(list_albums_threaded, current_app.app_context())

        files_in_album = files_in_album_future.result()
        album_names = list_albums_future.result()

    if isinstance(files_in_album, Response):
        return files_in_album
    
    return render_template("album.html", medias=files_in_album, albums=album_names, album=album_name)
