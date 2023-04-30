import azure.functions as func
from azure.identity import DefaultAzureCredential
from azure.storage.blob import BlobClient
import logging

app = func.FunctionApp()

# func azure functionapp publish wboyles-resizer

@app.function_name(name="Resizer")
@app.blob_trigger(arg_name="myblob", path="photos", connection="PhotosConnection")
def test_function(myblob: func.InputStream):
    logging.info(f"{myblob.name=}")
    logging.info(f"{myblob.uri=}")
    logging.info(f"Reading {myblob.length=} bytes")

    blob_bytes = myblob.read()
    logging.info(f"Found {len(blob_bytes)=} bytes")
    

    name = str(myblob.name).split("/")[-1]
    logging.info(f"{name=}")

    # # TODO: Either get this url from the input or from config
    account_url = "https://wboylesbackups.blob.core.windows.net"
    credential = DefaultAzureCredential()
    logging.info("Created credential")

    # src_client = BlobClient(account_url, "photos", name, credential=credential)
    des_client = BlobClient(account_url, "videos", name, credential=credential)

    des_client.upload_blob(blob_bytes)