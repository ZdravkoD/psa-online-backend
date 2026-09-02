import json
import logging
from azure.servicebus import ServiceBusClient, ServiceBusMessage
from bson import ObjectId

from configuration.common import AzureConfig
from messaging.messaging import ScraperTaskItem, TaskStatus

# Create a logger for this module
logger = logging.getLogger(__name__)


class TaskUpdatePublisher:
    """
    This class is responsible for publishing the task updates to the Azure Service Bus queue for task updates
    """

    def __init__(self):
        self.CONNECTION_STRING = AzureConfig.ServiceBusTasksUpdates.CONNECTION_STRING
        self.QUEUE_NAME = AzureConfig.ServiceBusTasksUpdates.QUEUE_NAME
        self.servicebus_client = ServiceBusClient.from_connection_string(conn_str=self.CONNECTION_STRING, logging_enable=True)

    def publish_error(self, taskItem: ScraperTaskItem, message: str, detailed_error_message: str, progress: int, image_urls: list[str] | None = None):
        taskItem.status.status = TaskStatus.ERROR
        taskItem.status.message = message
        taskItem.status.progress = progress
        taskItem.status.detailed_error_message = detailed_error_message
        taskItem.image_urls = image_urls

        self._publish(taskItem=taskItem)

    def publish_success(self, taskItem: ScraperTaskItem, report: dict):
        taskItem.status.status = TaskStatus.SUCCESS
        taskItem.status.message = "Задачата приключи успешно!"
        taskItem.status.progress = 100
        taskItem.report = report

        self._publish(taskItem=taskItem)

    def publish_progress_update(self, taskItem: ScraperTaskItem, message: str, progress: int):
        taskItem.status.message = message
        taskItem.status.progress = progress

        self._publish(taskItem=taskItem)

    def _publish(self, taskItem: ScraperTaskItem):
        try:
            self._send_message_to_servicebus_queue(json.dumps(taskItem.to_json()))
        except Exception as e:
            logger.error(f"TaskUpdatePublisher: Couldn't publish the message: {e}")

    def _send_message_to_servicebus_queue(self, message: str):
        with self.servicebus_client:
            sender = self.servicebus_client.get_queue_sender(queue_name=self.QUEUE_NAME)
            with sender:
                sb_message = ServiceBusMessage(message, content_type="application/json")
                sender.send_messages(sb_message)
                logger.info(f"Sent message to the Service Bus queue: {message}")
