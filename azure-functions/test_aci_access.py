from dotenv import load_dotenv
from azure.identity import DefaultAzureCredential
from azure.mgmt.containerinstance import ContainerInstanceManagementClient
from azure.core.exceptions import HttpResponseError

import os
import logging

print("Loading environment variables from .env file")
load_dotenv(".env")

# React App (Azure Static Web Apps)
# Azure Functions (Python)
# Azure Service Bus (Task Queue)
# Azure Container Instances (Docker)
# CosmosDB
# Azure Service Bus (Task Queue)
# Azure Functions (Python)
# React App (Azure Static Web Apps)
# Setting up a logger
logger = logging.getLogger('azure.identity')
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler()
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)
# Acquire a credential object
credentials = DefaultAzureCredential()

subscription_id = os.environ["AZURE_SUBSCRIPTION_ID"]
resource_group_name = os.environ["RESOURCE_GROUP_NAME"]
container_group_name = os.getenv("ACI_CONTAINER_GROUP_NAME", "psa-online-scraper")
client = ContainerInstanceManagementClient(credentials, subscription_id)

# Ensure instance_view is included in the fetched data
try:
    container_group = client.container_groups.get(resource_group_name, container_group_name)
    if isinstance(container_group, HttpResponseError):
        print(f"ТТТТТТ Container group {container_group_name} not found in resource group {resource_group_name}")
        print(container_group.response)
except HttpResponseError as e:
    print(f"СССССС Container group {container_group_name} not found in resource group {resource_group_name}")
    print(e.response.status_code)
    print(e.message)

print(client)
print(container_group_name)
