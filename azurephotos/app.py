from flask import Flask
from azure.identity import DefaultAzureCredential
from azure.storage.blob import BlobServiceClient
from azure.data.tables import TableServiceClient
import src.view.view as view
import src.api.api as api

def create_app() -> Flask:
    app = Flask(__name__)

    with app.app_context():
        credential = DefaultAzureCredential(exclude_cli_credential=True)
        account_name = "wboylesbackups"

        blob_account_url = f"https://{account_name}.blob.core.windows.net"
        blob_service_client = BlobServiceClient(blob_account_url, credential=credential)
        photos_container_client = blob_service_client.get_container_client("photos")
        videos_container_client = blob_service_client.get_container_client("videos")
        thumbnails_container_client = blob_service_client.get_container_client("thumbnails")

        table_account_url = f"https://{account_name}.table.core.windows.net"
        albums_table_client = TableServiceClient(
            table_account_url, credential=credential
        ).get_table_client("Albums2")

        app.config.update(
            credential=credential,
            account_name=account_name,
            blob_account_url=blob_account_url,
            blob_service_client=blob_service_client,
            photos_container_client=photos_container_client,
            videos_container_client=videos_container_client,
            thumbnails_container_client=thumbnails_container_client,
            albums_table_client=albums_table_client,
            SEND_FILE_MAX_AGE_DEFAULT=86400,
            MAX_CONTENT_LENGTH=200 * 1024 * 1024,  # 200 MB
        )
        for blueprint in view.blueprints:
            app.register_blueprint(blueprint)
        for blueprint in api.blueprints:
            app.register_blueprint(blueprint)

    return app


app = create_app()

if __name__ == "__main__":
    app.run()
