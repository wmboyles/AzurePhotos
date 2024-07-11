import asyncio

from azure.identity.aio import DefaultAzureCredential
from flask import Flask
from datetime import datetime, timedelta, timezone
from azure.storage.blob import ContainerSasPermissions, generate_container_sas
from azure.storage.blob.aio import BlobServiceClient

import src.view.view as view
import src.api.api as api


def create_app():
    app = Flask(__name__)

    event_loop = asyncio.get_event_loop()

    account_name = "wboylesbackups"
    blob_account_url = f"https://{account_name}.blob.core.windows.net"
    table_account_url = f"https://{account_name}.table.core.windows.net"
    thumbnails_container_name = "thumbnails"
    photos_container_name = "photos"

    credential=DefaultAzureCredential(
        exclude_cli_credential=True, exclude_shared_token_cache_credential=True
    )
    thumbnails_container_sas=event_loop.run_until_complete(
        get_container_sas(account_name, thumbnails_container_name, credential)
    )
    photos_container_sas=event_loop.run_until_complete(get_container_sas(account_name, photos_container_name, credential)
    )

    app.config.update(
        event_loop=event_loop,
        account_name=account_name,
        blob_account_url=blob_account_url,
        table_account_url=table_account_url,
        thumbnails_container_name=thumbnails_container_name,
        photos_container_name=photos_container_name,
        credential=credential,
        thumbnails_container_sas=thumbnails_container_sas,
        photos_container_sas=photos_container_sas,
    )

    for blueprint in view.blueprints:
        app.register_blueprint(blueprint)
    for blueprint in api.blueprints:
        app.register_blueprint(blueprint)

    app.app_context().push()

    return app


async def get_container_sas(account_name: str, container_name: str, credential: DefaultAzureCredential):
    blob_account_url = f"https://{account_name}.blob.core.windows.net"

    sas_start = datetime.now(timezone.utc) - timedelta(minutes=1)
    sas_end = datetime.now(timezone.utc) + timedelta(minutes=30)

    bsc = BlobServiceClient(blob_account_url, credential)

    user_delegation_key = await bsc.get_user_delegation_key(
        key_start_time=sas_start,
        key_expiry_time=sas_end,
    )

    container_sas = generate_container_sas(
        account_name=account_name,
        container_name=container_name,
        user_delegation_key=user_delegation_key,
        permission=ContainerSasPermissions(read=True),
        start=sas_start,
        expiry=sas_end,
    )

    return container_sas


if __name__ == "__main__":
    app = create_app()
    app.run()
