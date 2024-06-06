import json
import logging
from azure.servicebus import ServiceBusClient, ServiceBusMessage
from bson import ObjectId

from configuration.common import AzureConfig
from shared_lib.messaging.messaging import ScraperTaskUpdates, TaskStatus


class TaskUpdatePublisher:
    """
    This class is responsible for publishing the task updates to the Azure Service Bus queue for task updates
    """

    def __init__(self):
        self.CONNECTION_STRING = AzureConfig.ServiceBusTasksUpdates.CONNECTION_STRING
        self.QUEUE_NAME = AzureConfig.ServiceBusTasksUpdates.QUEUE_NAME
        self.servicebus_client = ServiceBusClient.from_connection_string(conn_str=self.CONNECTION_STRING, logging_enable=True)

    def publish_error(self, account_id: ObjectId, task_id: str, message: str, detailed_error_message: str, progress: int):
        self._publish(account_id, task_id, TaskStatus.ERROR, message, progress, detailed_error_message)

    def publish_success(self, account_id: ObjectId, task_id: str, message: str, progress: int):
        self._publish(account_id, task_id, TaskStatus.SUCCESS, message, progress)

    def publish_progress_update(self, account_id: ObjectId, task_id: str, message: str, progress: int):
        self._publish(account_id, task_id, TaskStatus.IN_PROGRESS, message, progress)

    def publish_final_report(self, account_id: ObjectId, task_id: str, message: str, progress: int):
        self._publish(account_id, task_id, TaskStatus.FINAL_REPORT, message, progress)

    def _publish(self,
                 account_id: ObjectId,
                 task_id: str,
                 status: TaskStatus,
                 message: str,
                 progress: int,
                 detailed_error_message: str | None = None):
        # print the types of the arguments received:
        print("Publishing task update:")
        print(f"account_id: {type(account_id)}")
        print(f"task_id: {type(task_id)}")
        print(f"status: {type(status)}")
        print(f"message: {type(message)}")
        print(f"progress: {type(progress)}")
        print(f"detailed_error_message: {type(detailed_error_message)}")

        update_message = ScraperTaskUpdates(
            account_id=account_id,
            task_id=task_id,
            status=status.value,
            message=message,
            progress=progress,
            detailed_error_message=detailed_error_message,
        )
        if detailed_error_message:
            update_message.detailed_error_message = detailed_error_message

        print("Printing types of the fields of update_message")
        print(f"account_id: {type(update_message.account_id)}")
        print(f"task_id: {type(update_message.task_id)}")
        print(f"status: {type(update_message.status)}")
        print(f"message: {type(update_message.message)}")
        print(f"progress: {type(update_message.progress)}")
        print(f"detailed_error_message: {type(update_message.detailed_error_message)}")

        try:
            self._send_message_to_servicebus_queue(json.dumps(update_message.to_json()))
        except Exception as e:
            logging.error(f"TaskUpdatePublisher: Couldn't publish the message: {e}")

    def _send_message_to_servicebus_queue(self, message: str):
        with self.servicebus_client:
            sender = self.servicebus_client.get_queue_sender(queue_name=self.QUEUE_NAME)
            with sender:
                sb_message = ServiceBusMessage(message, content_type="application/json")
                sender.send_messages(sb_message)
                logging.info(f"Sent message to the Service Bus queue: {message}")
