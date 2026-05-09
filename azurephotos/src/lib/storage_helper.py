from datetime import datetime, timedelta, timezone
from flask import current_app
from azure.storage.blob import (
    ContainerSasPermissions,
    generate_container_sas,
    BlobServiceClient,
)
from .refresher import refreshed

@refreshed(every=timedelta(minutes=15))
def get_container_sas(container_name: str) -> str:
    now = datetime.now(timezone.utc)
    sas_start = now - timedelta(minutes=1)
    sas_end = now + timedelta(minutes=30)

    bsc: BlobServiceClient = current_app.config["blob_service_client"]
    user_delegation_key = bsc.get_user_delegation_key(
        key_start_time=sas_start,
        key_expiry_time=sas_end
    )

    return generate_container_sas(
        account_name=str(bsc.account_name),
        container_name=container_name,
        user_delegation_key=user_delegation_key,
        permission=ContainerSasPermissions(read=True),
        start=sas_start,
        expiry=sas_end,
    )
