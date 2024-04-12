# psa-online-backend
Backend code for Pharmacy Stock Automation.

## Runing the Azure Functinos locally

1. Install dependencies:
```bash
brew tap azure/functions
brew install azure-functions-core-tools@4
python -m venv .venv
source .venv/bin/activate

cd azure-functions
pip install -r requirements.txt
```
2. Start Azure Functions:
```bash
cd azure-functions
func start
```


## Infra Setup

This repo uses Azure Cloud for its deployment.

### Azure Functions

Used to implement the REST API.

### Azure CosmosDB

Used to store all account information and historical task statuses and outcomes.

### Azure Blob storage

Storing all uploaded files by users.

### Azure Service Bus

Used for task queues, retrying "dead" tasks, etc.

### Azure Container Instances

For starting up Python Selenium workers that work on the tasks.

### Azure Static Web Apps

For deploying the React web app in repository psa-online-frontend


