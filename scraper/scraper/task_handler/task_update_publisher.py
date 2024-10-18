import json
import logging
from azure.servicebus import ServiceBusClient, ServiceBusMessage
from bson import ObjectId

from configuration.common import AzureConfig
from messaging.messaging import ScraperTaskItemStatus, ScraperTaskUpdates, TaskStatus

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

    def publish_error(self, account_id: ObjectId, task_id: str, message: str, detailed_error_message: str, progress: int, image_urls: list[str] | None = None):
        self._publish(
            account_id,
            task_id,
            ScraperTaskItemStatus(status=TaskStatus.ERROR, message=message, progress=progress, detailed_error_message=detailed_error_message),
            None,
            image_urls)

    def publish_success(self, account_id: ObjectId, task_id: str, message: str, progress: int, report: dict):
        self._publish(
            account_id,
            task_id,
            ScraperTaskItemStatus(status=TaskStatus.SUCCESS, message=message, progress=progress),
            report,
            None)

    def publish_progress_update(self, account_id: ObjectId, task_id: str, message: str, progress: int):
        self._publish(
            account_id,
            task_id,
            ScraperTaskItemStatus(status=TaskStatus.IN_PROGRESS, message=message, progress=progress),
            None,
            None)

    def _publish(self,
                 account_id: ObjectId,
                 task_id: str,
                 status: ScraperTaskItemStatus,
                 report: dict | None,
                 image_urls: list[str] | None):
        update_message = ScraperTaskUpdates(
            account_id=account_id,
            task_id=task_id,
            status=status,
            report=report,
            image_urls=image_urls
        )

        try:
            self._send_message_to_servicebus_queue(json.dumps(update_message.to_json()))
        except Exception as e:
            logger.error(f"TaskUpdatePublisher: Couldn't publish the message: {e}")

    def _send_message_to_servicebus_queue(self, message: str):
        with self.servicebus_client:
            sender = self.servicebus_client.get_queue_sender(queue_name=self.QUEUE_NAME)
            with sender:
                sb_message = ServiceBusMessage(message, content_type="application/json")
                sender.send_messages(sb_message)
                logger.info(f"Sent message to the Service Bus queue: {message}")
