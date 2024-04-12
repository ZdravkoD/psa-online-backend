from datetime import datetime
import os
import azure.functions as func
from azure.servicebus import ServiceBusClient, ServiceBusMessage
import logging

app = func.FunctionApp()


@app.route(route="queue-task", auth_level=func.AuthLevel.ANONYMOUS, methods=["GET"])
def queue_task(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Python HTTP trigger function processed a request.')

    name = req.params.get('name')
    if not name:
        try:
            req_body = req.get_json()
        except ValueError:
            pass
        else:
            name = req_body.get('name')

    if name:
        send_message_to_servicebus_queue({"task_name": name,
                                          "task_created_at": datetime.now().isoformat(),
                                          "task_created_by": "Azure Function",
                                          "task_status": "Created"})
        return func.HttpResponse(f"Hello, {name}. This HTTP triggered function executed successfully.")
    else:
        return func.HttpResponse(
             "This HTTP triggered function executed successfully." +
             " Pass a name in the query string or in the request body for a personalized response.",
             status_code=200
        )


def send_message_to_servicebus_queue(message: dict):
    CONNECTION_STR = os.getenv("psaonline_SERVICEBUS", "")
    QUEUE_NAME = os.getenv("psaonline_SERVICEBUS_QUEUE", "")
    servicebus_client = ServiceBusClient.from_connection_string(conn_str=CONNECTION_STR, logging_enable=True)
    with servicebus_client:
        sender = servicebus_client.get_queue_sender(queue_name=QUEUE_NAME)
        with sender:
            sb_message = ServiceBusMessage(str(message))
            sender.send_messages(sb_message)
            logging.info(f"Sent message to the Service Bus queue: {message}")
