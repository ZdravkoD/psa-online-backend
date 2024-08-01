import json
import signal
import threading
from typing import List
from azure.servicebus import ServiceBusClient, ServiceBusReceivedMessage

from configuration.common import AzureConfig
from messaging.messaging import ScraperTaskItem
from task_handler.task_handler import TaskHandler

shutdown_event = threading.Event()


def handle_sigterm(signum, frame):
    print("SIGTERM received, initiating shutdown...")
    shutdown_event.set()


def process_service_bus_messages():
    with ServiceBusClient.from_connection_string(AzureConfig.ServiceBusTasks.CONNECTION_STRING) as client:
        with client.get_queue_receiver(AzureConfig.ServiceBusTasks.QUEUE_NAME) as receiver:
            while not shutdown_event.is_set():
                messages: List[ServiceBusReceivedMessage] = receiver.receive_messages(max_message_count=1, max_wait_time=5)
                for message in messages:
                    # Decode message body from bytes to string
                    message_body_bytes = b''.join(message.body)
                    message_body_str = message_body_bytes.decode('utf-8')
                    print("Received message as string: " + message_body_str)
                    message_body_json = json.loads(message_body_str)
                    print(f"Received message as JSON: {message_body_json}")

                    print("processing message...")
                    TaskHandler(ScraperTaskItem.from_dict(message_body_json)).handle_task()
                    print("message processed.")

                    receiver.complete_message(message)
                # Optional: Perform other tasks or checks
            print("No longer receiving messages, exiting thread...")


def main():
    print("Application started.")

    # Setup the signal handler for graceful shutdown
    signal.signal(signal.SIGTERM, handle_sigterm)

    # Start the message processing thread
    thread = threading.Thread(target=process_service_bus_messages)
    thread.start()

    # Wait for the thread to complete
    thread.join()
    print("Application is shutting down.")


if __name__ == "__main__":
    main()
