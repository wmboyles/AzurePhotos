from azure.identity.aio import DefaultAzureCredential
from datetime import datetime, timedelta, timezone
from azure.storage.blob import ContainerSasPermissions, generate_container_sas
from azure.storage.blob.aio import BlobServiceClient
from azure.data.tables.aio import TableServiceClient, TableClient


def build_credential() -> DefaultAzureCredential:
    return DefaultAzureCredential(
        exclude_cli_credential=True, exclude_shared_token_cache_credential=True
    )


async def get_container_sas(
    account_name: str, container_name: str, credential: DefaultAzureCredential
):
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
