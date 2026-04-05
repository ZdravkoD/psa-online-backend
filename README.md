# psa-online-backend
Backend code for Pharmacy Stock Automation.

## Doing staging/prod manual tests

1. Always run then against Толстой.



## Running locally


### Start Python in a venv

```bash
source ./.venv/bin/activate
```


## Runing the Azure Functinos locally

1. Install dependencies:
```bash
cd azure-functions
brew tap azure/functions
brew install azure-functions-core-tools@4

python -m venv .venv
source .venv/bin/activate

pip install -r requirements.txt
```
2. Start Azure Functions:
```bash
cd azure-functions
func start
```

## Read-only smoke tests

This repo includes a read-only smoke test for the deployed Azure Functions app.
It only calls `GET` endpoints and intentionally avoids any endpoint that creates
or updates data.

```bash
cd azure-functions
make smoke-test BASE_URL=https://psa-online-functions.azurewebsites.net/api
```

The script currently checks:

- `GET /pharmacies`
- `GET /distributors`
- `GET /products?limit=1`
- `GET /task/not-a-valid-object-id` expecting `400`
- `GET /product/not-a-valid-object-id` expecting `400`


## Infra Setup

This repo uses Azure Cloud for its deployment.

### Azure Functions

Used to implement the REST API.
Link: [Azure Functions](https://portal.azure.com/#@kfzzdravkogmail.onmicrosoft.com/resource/subscriptions/7b4dbc02-6b4b-42bf-90b2-92d8ed681e87/resourceGroups/psa/providers/Microsoft.Web/sites/psa-online-functions/appServices)

### Azure CosmosDB

Used to store all account information and historical task statuses and outcomes.

### Azure Blob storage

Storing all uploaded files by users.

### Azure Service Bus

Used for task queues, retrying "dead" tasks, etc.
Link: [Service Bus](https://portal.azure.com/#@kfzzdravkogmail.onmicrosoft.com/resource/subscriptions/7b4dbc02-6b4b-42bf-90b2-92d8ed681e87/resourceGroups/psa/providers/Microsoft.ServiceBus/namespaces/psa-online/queues/task-queue/explorer)

### Azure Container Instances

For starting up Python Selenium workers that work on the tasks.
Link: [Azure Container Instance](https://portal.azure.com/#@kfzzdravkogmail.onmicrosoft.com/resource/subscriptions/7b4dbc02-6b4b-42bf-90b2-92d8ed681e87/resourcegroups/psa/providers/Microsoft.ContainerInstance/containerGroups/psa-online-scraper/overview)

### Azure Static Web Apps

For deploying the React web app in repository psa-online-frontend

### Azure Web PubSub

For reporting real-time status from the Selenium worker to the web application.
