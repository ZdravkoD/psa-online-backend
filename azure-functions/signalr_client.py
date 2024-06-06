import os
import jwt
import requests
import time
from urllib.parse import quote_plus
from dotenv import load_dotenv


"""
This class is used to send messages to Azure SignalR Service.

Currently this class is not used. It is just a reference for how to send messages to Azure SignalR Service.

We're using Azure PubSub instead of Azure SignalR Service.
"""


class AzureSignalRClient:
    def __init__(self):
        print([var for var in os.environ if var.startswith("AZURE_SIGNALR")])
        self.access_key = os.environ["AZURE_SIGNALR_ACCESS_KEY"]
        self.endpoint = os.environ["AZURE_SIGNALR_ENDPOINT"]
        self.hub_name = "all"
        self.target = "task_status_update"

    def send_signalr_task_status_update_message(self, hub_name, arguments):
        audience = f"{self.endpoint}/api/v1/hubs/{quote_plus(hub_name)}"
        token = self.generate_jwt(audience, self.access_key)
        # TODO: Figure out how to send messages to specific users
        # url = f"{audience}/users/all"
        url = f"{audience}"
        print("Token:", token)
        print("Access Key:", self.access_key)
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        payload = {
            "target": self.target,
            "arguments": [arguments]
        }
        print("URL: ", url)
        print("Payload: ", payload)
        print("Headers: ", headers)
        response: requests.Response = requests.post(url, json=payload, headers=headers)
        return response.status_code, response.reason, response.ok

    def generate_jwt(self, audience, access_key, expire_in=3600):
        token = jwt.encode({
            'aud': audience,
            'iat': int(time.time()),
            'exp': int(time.time()) + expire_in
        }, access_key, algorithm='HS256')
        return token


# Usage example
load_dotenv()
arguments = {"task_id": "12345", "status": "Completed"}
status_code, response_text, response_ok = AzureSignalRClient().send_signalr_task_status_update_message("all", arguments)
print(f"Response Status: {status_code}, Response: {response_text}, Response OK: {response_ok}")
