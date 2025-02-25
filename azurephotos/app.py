from flask import Flask
from azure.identity import DefaultAzureCredential
import src.view.view as view
import src.api.api as api


def create_app():
    app = Flask(__name__)
    account_name = "wboylesbackups"

    with app.app_context():
        app.config.update(
            credential=DefaultAzureCredential(exclude_cli_credential=True),
            account_name=account_name,
            thumbnails_container_name="thumbnails",
            photos_container_name="photos",
            albums_table_name="Albums2",
        )

        for blueprint in view.blueprints:
            app.register_blueprint(blueprint)
        for blueprint in api.blueprints:
            app.register_blueprint(blueprint)

    return app


app = create_app()

if __name__ == "__main__":
    app.run()
