# Azure Photos

Azure Photos is my personal photo storage solution since I had Azure credits through work and didn't want to pay for Google Photos.
It leverages Azure App Service, Azure Functions, and of course Azure Blob Storage.

## Running Locally

All commands should be run from the project root unless otherwise specified.

### Common Prerequisites

You should have the following installed
* Python 3.10
* Azure CLI
* Azure Functions Core Tools

Install the Python dependencies:
```ps
pip install -r requirements.txt
pip install -r requirements.dev.txt
```

Log in to Azure using the Azure CLI
```ps
Connect-AzAccount
```

### AzurePhotos WebApp

Run the following PowerShell commands:
```ps
cd azurephotos
flask run --debug --host=localhost --port=5000
```

### Photo Resizer Function

Run the following PowerShell commands:
```ps
cd wboyles-resizer
func start
```

## Deploying to Azure

All commands should be run from the project root unless otherwise specified.

### Common Prerequisites

You should have the following installed
* Azure CLI

### AzurePhotos WebApp

Run the following PowerShell commands:
```ps
Compress-Archive -Path azurephotos/* -DestinationPath azurephotos.zip
az webapp deploy --resource-group azure-photos --name azurephotos --src-path .\azurephotos.zip
rm azurephotos.zip
```

### Photo Resizer Function

Run the following PowerShell commands:
```ps
cd wboyles-resizer
func azure functionapp publish wboyles-resizer
```