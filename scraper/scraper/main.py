from psa_logger.logger import setup_logging  # noqa
setup_logging()  # noqa

import logging
from task_handler.task_handler import TaskHandler
from messaging.messaging import ScraperTaskItem
from configuration.common import AzureConfig
from azure.servicebus import ServiceBusClient, ServiceBusReceivedMessage, AutoLockRenewer
from typing import List
import threading
import signal
import json

shutdown_event = threading.Event()


# Create a logger for this module
logger = logging.getLogger(__name__)


def handle_sigterm(signum, frame):
    logger.exception("SIGTERM received, initiating shutdown...")
    shutdown_event.set()


def work_loop():
    while not shutdown_event.is_set():
        try:
            process_service_bus_messages()
        except Exception as e:
            logger.exception(f"Error in main loop: {e}")

    logger.info("No longer receiving messages, exiting thread...")


def process_service_bus_messages():
    with ServiceBusClient.from_connection_string(AzureConfig.ServiceBusTasks.CONNECTION_STRING) as client:
        with client.get_queue_receiver(queue_name=AzureConfig.ServiceBusTasks.QUEUE_NAME, auto_lock_renewer=AutoLockRenewer(max_lock_renewal_duration=3000)) as receiver:
            while not shutdown_event.is_set():
                messages: List[ServiceBusReceivedMessage] = receiver.receive_messages(max_message_count=1, max_wait_time=5)
                for message in messages:
                    # Decode message body from bytes to string
                    message_body_bytes = b''.join(message.body)
                    message_body_str = message_body_bytes.decode('utf-8')
                    logger.info("Received message as string: " + message_body_str)
                    message_body_json = json.loads(message_body_str)
                    logger.info(f"Received message as JSON: {message_body_json}")

                    logger.info("processing message...")
                    TaskHandler(ScraperTaskItem.from_dict(message_body_json)).handle_task()
                    logger.info("message processed.")

                    receiver.complete_message(message)


def main():
    logger.info("Application started.")

    # Setup the signal handler for graceful shutdown
    signal.signal(signal.SIGTERM, handle_sigterm)

    # Start the message processing thread
    thread = threading.Thread(target=work_loop)
    thread.start()

    # Wait for the thread to complete
    thread.join()
    logger.info("Application is shutting down.")


if __name__ == "__main__":
    main()
