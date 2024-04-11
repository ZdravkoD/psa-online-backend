# psa-online-backend
Backend code for Pharmacy Stock Automation.

## Setup

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


