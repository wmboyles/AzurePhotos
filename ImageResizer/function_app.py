import logging
from io import BytesIO

import azure.functions as func
from azure.identity import DefaultAzureCredential
from azure.storage.blob import BlobClient
from PIL import Image

app = func.FunctionApp()

# func azure functionapp publish wboyles-resizer


# TODO: Handle not processing non-image files.
# Could we somehow look at content-type?
# Maybe just if file extension is in (Image.OPEN.keys() & Image.SAVE.keys()), with a try/catch if PIL throws an error when reading
@app.function_name(name="Resizer")
@app.blob_trigger(arg_name="myblob", path="photos", connection="PhotosConnection")
def test_function(myblob: func.InputStream):
    logging.info(f"{myblob.name=}")
    logging.info(f"{myblob.uri=}")

    blob_bytes = BytesIO(myblob.read())
    logging.info(f"Read blob into BytesIO object")

    name = str(myblob.name).split("/")[-1]
    logging.info(f"{name=}")

    try:
        with Image.open(blob_bytes) as img:
            logging.info("Resizing image")
            img.thumbnail((370, 280))

            # TODO: Either get this url from the input or from config
            account_url = "https://wboylesbackups.blob.core.windows.net"
            credential = DefaultAzureCredential()
            logging.info("Created credential")

            des_client = BlobClient(account_url, "videos", name, credential=credential)
            logging.info("Created destination BlobClient")

            buffer = BytesIO()
            img.save(buffer, img.format)
            logging.info("Saved resized image to buffer")

            # TODO: Get content-type info from input and copy it when uploading
            # TODO: Would it be better to use the blob output binding?
            des_client.upload_blob(buffer.getvalue())
            logging.info("Uploaded to desination container")
    except Exception as e:
        logging.error(e)
        raise e
