import asyncio
from flask import Flask
from src.storage_helper import get_container_sas, build_credential
import src.view.view as view
import src.api.api as api


def create_app():
    app = Flask(__name__)

    credential = build_credential()

    account_name = "wboylesbackups"
    thumbnails_container_name = "thumbnails"
    photos_container_name = "photos"

    with app.app_context():
        app.config.update(
            credential = credential,
            account_name = account_name,
            blob_account_url = f"https://{account_name}.blob.core.windows.net",
            table_account_url = f"https://{account_name}.table.core.windows.net",
            thumbnails_container_name = thumbnails_container_name,
            photos_container_name = photos_container_name,
            albums_table_name = "Albums",
            thumbnails_container_sas = asyncio.run(
                get_container_sas(account_name, thumbnails_container_name, credential)
            ),
            photos_container_sas = asyncio.run(
                get_container_sas(account_name, photos_container_name, credential)
            ),
        )

        for blueprint in view.blueprints:
            app.register_blueprint(blueprint)
        for blueprint in api.blueprints:
            app.register_blueprint(blueprint)

    return app


if __name__ == "__main__":
    app = create_app()
    app.run()
