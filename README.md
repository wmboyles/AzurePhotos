# Azure Photos

Azure Photos is my personal cloud-based photo and video storage solution.
I have Azure credits through work, and I don't want to pay for Google Photos.
It leverages Azure App Service and of course Azure Blob Storage.

## Dev Setup

### Software to Install

* Python 3.14
* Azure CLI
* (Optional): Jupyter, ipykernel for notebooks

### Running Locally

All commands should be run from the project root unless otherwise specified.

Log in to Azure using the Azure CLI
```ps
Connect-AzAccount -TenantId 15a87ef6-f442-4382-96fc-8003a45ef258
```

Install all requirements
```
pip install -r requirements-dev.txt
```

Run the app locally
```ps
cd azurephotos
flask run --debug --host=localhost --port=5000
```

## Testing

You should have all the required software from dev setup before testing.

```ps
pytest
```

## Deployment

You should have all the required software from dev setup before deploying.

Build the project
```ps
python build.py
```

This will create a zip file in the `out/` directory called `azurephotos-<sha>.zip`, where `<sha>` is the git SHA of the current commit.
```ps
az login --scope https://management.core.windows.net/.default 
az webapp deploy --resource-group azure-photos --name azurephotos --src-path .\out\azurephotos.zip --type zip
```

The command _should_ complete successfully. However, sometimes you may get a 504 (Gateway Timeout) even when the deployment eventually succeeds.
In this case, you'll need to view the recent deployments in the Azure portal to get the correct status.
