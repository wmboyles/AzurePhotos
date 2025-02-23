# Azure Photos

Azure Photos is my personal photo storage solution since I had Azure credits through work and didn't want to pay for Google Photos.
It leverages Azure App Service, Azure Functions, and of course Azure Blob Storage.

## Dev Setup

### Software to Install

* Python 3.12+
* Azure CLI
* Azure Functions Core Tools
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

#### Photo Resizer

Everything is inside the `wboyles-resizer` directory
```ps
cd wboyles-resizer
```
All of the rest of the commands in this section will be from this directory.

Install all requirements
```
pip install -r requirements.txt
```

Run the function locally
```ps
func start
```

## Deployment

You should have all the required software from dev setup before deploying.

### AzurePhotos WebApp

```ps
Compress-Archive -Path azurephotos/* -DestinationPath azurephotos.zip
az webapp deploy --resource-group azure-photos --name azurephotos --src-path .\azurephotos.zip --type zip
rm azurephotos.zip
```

### Photo Resizer Function

```ps
cd wboyles-resizer
func azure functionapp publish wboyles-resizer
```