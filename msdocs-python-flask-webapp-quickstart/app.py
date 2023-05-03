from flask import Flask, render_template, request
from azure.identity import DefaultAzureCredential
from azure.storage.blob import BlobServiceClient, BlobClient, generate_blob_sas, BlobSasPermissions
from datetime import datetime, timedelta

app = Flask(__name__)
credential = DefaultAzureCredential()


@app.route("/")
def index():
    account_name = "wboylesbackups"
    account_url = f"https://{account_name}.blob.core.windows.net"
    container_name = "photos"
    blob_name = "20220304_123030.jpg"

    bsc = BlobServiceClient(account_url, credential)
    start = datetime.utcnow() - timedelta(minutes=1)
    end = datetime.utcnow() + timedelta(hours=1)
    udk = bsc.get_user_delegation_key(
        key_start_time=start,
        key_expiry_time=end,
    )
    blob_sas = generate_blob_sas(
        account_name, 
        container_name, 
        blob_name, 
        user_delegation_key=udk,
        permission=BlobSasPermissions(read=True),
        start=start,
        expiry=end,
    )
    blob_client = BlobClient(
        account_url, container_name, blob_name, credential=credential
    )
    url = f"{blob_client.url}?{blob_sas}"

    name = request.headers.get("X-MS-CLIENT-PRINCIPAL-NAME", "DEV")
    return render_template("index.html", name=name, imgurl=url)


if __name__ == "__main__":
    app.run()
