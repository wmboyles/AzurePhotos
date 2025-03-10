from azure.identity import DefaultAzureCredential
from datetime import datetime, timedelta, timezone
from azure.storage.blob import (
    ContainerSasPermissions,
    generate_container_sas,
    BlobServiceClient,
)
from azure.data.tables import TableServiceClient, TableClient
from .credential_refresher import refreshed

@refreshed(every=timedelta(minutes=15))
def get_container_sas(
    account_name: str, container_name: str, credential: DefaultAzureCredential
) -> str:
    blob_account_url = f"https://{account_name}.blob.core.windows.net"

    now = datetime.now(timezone.utc)
    sas_start = now - timedelta(minutes=1)
    sas_end = now + timedelta(minutes=30)

    bsc = BlobServiceClient(blob_account_url, credential)

    user_delegation_key = bsc.get_user_delegation_key(
        key_start_time=sas_start, key_expiry_time=sas_end
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


def get_table_client(
    account_name: str, table_name: str, credential: DefaultAzureCredential
) -> TableClient:
    """
    Built a TableClient for an account and

    - account_name: Storage account name
    - table_name: Name of table in storage account
    - credential: Credential for storage account
    """

    table_service_client = TableServiceClient(
        endpoint=f"https://{account_name}.table.core.windows.net", credential=credential
    )
    table_client = table_service_client.get_table_client(table_name)

    return table_client
