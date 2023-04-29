import azure.functions as func
from azure.identity import DefaultAzureCredential
from azure.storage.blob import BlobClient
import logging

app = func.FunctionApp()


@app.function_name(name="Resizer")
@app.blob_trigger(arg_name="myblob", path="photos", connection="PhotosConnection")
def test_function(myblob: func.InputStream):
    logging.info(f"Savan Says: {myblob.name=}")
    logging.info(f"Savan Says: {myblob.uri=}")
    name = str(myblob.name).split("/")[-1]
    logging.info(f"Savan Says: {name=}")
    account_url = "https://wboylesbackups.blob.core.windows.net"
    credential = DefaultAzureCredential()

    src_client = BlobClient(account_url, "photos", name, credential=credential)
    des_client = BlobClient(account_url, "videos", name, credential=credential)

    des_client.start_copy_from_url(src_client.url)