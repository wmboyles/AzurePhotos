# Azure Photos

Azure Photos is my personal cloud-based photo and video storage solution.
I have Azure credits through work, and I don't want to pay for Google Photos.
It leverages Azure App Service and of course Azure Blob Storage.

## Dev Setup

### Software to Install

* Python 3.14
* Azure CLI

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

This will run all the tests and produce a coverage report in the `htmlcov` directory.
The `test.yml` workflow will also run these same actions on PRs to main and generate a coverage report.


## Deployment

The `build.yml` workflow will run automatically when a commit is merged to main and produce artifacts.
Find the run id of the build.yml version you want to deploy, then provide it as input to the `release.yml` workflow.
The workflow will take care of federating from GitHub to Azure and deploying the artifacts.
