# Azure Photos

Azure Photos is my personal photo storage solution since I had Azure credits through work and didn't want to pay for Google Photos.
It leverages Azure App Service and of course Azure Blob Storage.

## Dev Setup

### Software to Install

* Python 3.12+
* Azure CLI
* (Optional): Jupyter, ipykernel for notebooks

### Running Locally

All commands should be run from the project root unless otherwise specified.

Log in to Azure using the Azure CLI
```ps
Connect-AzAccount
```

#### AzurePhotos WebApp

Everything is inside the `azurephotos` directory.
```ps
cd azurephotos
```
All of the rest of the commands in this section will be from this directory.

Install all requirements
```
pip install -r requirements.txt
```

Run the app locally:
```ps
flask run --debug --host=localhost --port=5000
```

## Deployment

You should have all the required software from dev setup before deploying.

### AzurePhotos WebApp

```ps
az login --scope https://management.core.windows.net//.default 
Compress-Archive -Path azurephotos/* -DestinationPath azurephotos.zip
az webapp deploy --resource-group azure-photos --name azurephotos --src-path .\azurephotos.zip --type zip
rm azurephotos.zip
```

The command _should_ complete successfully. However, sometimes you may get a 504 (Gateway Timeout) when the deployment eventually succeeds.
In this case, you'll need to view the recent deployments in the Azure portal to get the correct status.