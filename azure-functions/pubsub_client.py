import os
from azure.messaging.webpubsubservice import WebPubSubServiceClient
from azure.core.credentials import AzureKeyCredential


class AzureWebPubSubServiceClient:
    def __init__(self):
        self.endpoint = os.getenv("AZURE_WEB_PUBSUB_ENDPOINT", "")
        self.access_key = os.getenv("AZURE_WEB_PUBSUB_ACCESS_KEY", "")
        print("Endpoint:", self.endpoint)

    def send_task_update_to_all(self, message: dict):
        hub_name = "task_status_updates"
        # Create a WebPubSubServiceClient
        credential = AzureKeyCredential(self.access_key)
        client = WebPubSubServiceClient(endpoint=self.endpoint, credential=credential, hub=hub_name)  # type: ignore

        # Send a text message to all connected clients in the specified hub
        # TODO: Figure out how to send messages to specific users
        client.send_to_all(message)

        print("Message sent successfully")


# load_dotenv()

# # Your message to send
# message = {"task_id": "12345", "status": "Completed"}
# AzureWebPubSubServiceClient().send_task_update_to_all(message)
