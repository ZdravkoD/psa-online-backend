from enum import Enum
from typing import List

from bson import ObjectId


class FileType(str, Enum):
    JSON_CONTENT = "json_content"
    BLOB_STORAGE_URL = "blob_storage_url"


class ScraperTaskActionType(str, Enum):
    RESUME = "resume"
    START_OVER = "start_over"


class DistributorTypes(str, Enum):
    STING = "sting"
    PHOENIX = "phoenix"


class TaskStatus(str, Enum):
    ERROR = "error"
    SUCCESS = "success"
    IN_PROGRESS = "in progress"


class ScraperTaskItemStatus:
    def __init__(self, status: TaskStatus, message: str, progress: int, detailed_error_message=None):
        self.status = status
        self.message = message
        self.progress = progress
        self.detailed_error_message = detailed_error_message

    def to_json(self):
        return {
            "status": self.status.value,
            "message": self.message,
            "progress": self.progress,
            "detailed_error_message": self.detailed_error_message,
        }


class ScraperTaskUpdates:
    def __init__(self, account_id: ObjectId, task_id: str, status: ScraperTaskItemStatus, report: dict | None, image_urls: list[str] | None = None):
        self.account_id = account_id
        self.task_id = task_id
        self.status = status
        self.report = report
        self.image_urls = image_urls

    def _validate(self):
        if not isinstance(self.account_id, ObjectId):
            raise ValueError("Account ID must be an ObjectId")
        if len(str(self.account_id)) == 0:
            raise ValueError("Account ID must not be empty")
        if not isinstance(self.task_id, str):
            raise ValueError("Task ID must be a string")
        if len(self.task_id) == 0:
            raise ValueError("Task ID must not be empty")

    def to_json(self):
        return {
            "account_id": str(self.account_id),
            "task_id": str(self.task_id),
            "status": self.status.to_json(),
            "report": self.report,
            "image_urls": self.image_urls
        }


class ScraperTaskItem:
    status: ScraperTaskItemStatus

    def __init__(self,
                 account_id: ObjectId,
                 file_name: str,
                 file_data: str,
                 file_type: FileType,
                 pharmacy_id: str,
                 distributors: List[DistributorTypes],
                 task_type: ScraperTaskActionType,
                 date_created: str,
                 date_updated: str,
                 report: dict | None,
                 image_urls: list[str] | None = None):
        """
        :param account_id: The account ID of the user who requested the task
        :param file_name: The name of the file - this is used for logging purposes
        :param file_data: The data of the file - this is either JSON content or a URL to blob storage
            if JSON content, the format must be:
            {"rows": [{"product_name": "product 1", "quantity": 10}, {"product_name": "product 2", "quantity": 20}]}
        :param file_type: The type of the file - json_content or blob_storage_url
        :param pharmacy_id: The ID of the pharmacy to order items for
        :param distributors: The list of distributors to scrape
        :param task_type: The type of the task - "resume" or "start_over"

        Example message:
        {
            "account_id": "345",
            "file_name": "test_json",
            "file_data": "{\"rows\": [{\"product_name\": \"product 1\", \"quantity\": 10}, {\"product_name\": \"product 2\", \"quantity\": 20}]}",
            "file_type": "json_content",
            "pharmacy_id": "2075077",
            "distributors": ["sting", "phoenix"],
            "task_type": "start_over",
            "date_created": "2024-09-09T03:30:31Z",
            "date_updated": "2024-09-09T03:30:31Z",
        }
        """
        self.id: str = ""
        self.account_id = account_id
        self.file_name = file_name
        self.file_data = file_data
        self.file_type = file_type
        self.pharmacy_id = pharmacy_id
        self.distributors = distributors
        self.task_type = task_type
        self.date_created = date_created
        self.date_updated = date_updated
        self.report = report
        self.image_urls = image_urls

        self._validate()

    def _validate(self):
        if not isinstance(self.account_id, ObjectId):
            raise ValueError("Account ID must be a ObjectId")
        if len(str(self.account_id)) == 0:
            raise ValueError("Account ID must not be empty")
        if not isinstance(self.file_name, str):
            raise ValueError("File name must be a string")
        if not isinstance(self.file_data, str) and not isinstance(self.file_data, dict):
            raise ValueError("File name data be either a string or a json")
        if len(self.file_data) == 0:
            raise ValueError("File name must not be empty")
        if not isinstance(self.file_type, FileType):
            raise ValueError("File type must be a FileType")

        if not isinstance(self.pharmacy_id, str):
            raise ValueError("pharmacy_id must be a string")
        if len(self.pharmacy_id) == 0:
            raise ValueError("pharmacy_id must not be empty")

        if len(self.distributors) == 0:
            raise ValueError("Distributors must be a list of DistributorTypes with at least one element")
        if not isinstance(self.distributors, list):
            raise ValueError("Distributors must be a list")
        if not all(hasattr(DistributorTypes, distributor.upper()) for distributor in self.distributors):
            types = [(type(distributor), hasattr(DistributorTypes, distributor.upper())) for distributor in self.distributors]
            raise ValueError("Distributors must be a list of DistributorTypes, but types are: " + str(types))

        if not isinstance(self.task_type, ScraperTaskActionType):
            raise ValueError("Task type must be a ScraperTaskActionType")

    # JSON representation of the object
    def to_json(self):
        result = {
            "account_id": str(self.account_id),
            "file_name": self.file_name,
            "file_data": self.file_data,
            "file_type": self.file_type.value,
            "pharmacy_id": self.pharmacy_id,
            "distributors": self.distributors,
            "task_type": self.task_type.value,
            "date_created": self.date_created,
            "date_updated": self.date_updated,
            "status": self.status.to_json(),
            "report": self.report,
            "image_urls": self.image_urls
        }
        if self.id:
            result["_id"] = str(self.id)
        return result

    def to_update_dict(self):
        result = {
            "account_id": ObjectId(self.account_id),
            "file_name": self.file_name,
            "file_data": self.file_data,
            "file_type": self.file_type.value,
            "pharmacy_id": self.pharmacy_id,
            "distributors": self.distributors,
            "task_type": self.task_type.value,
            "date_created": self.date_created,
            "date_updated": self.date_updated,
            "status": self.status,
            "report": self.report,
            "image_urls": self.image_urls
        }
        return result

    @classmethod
    def from_dict(cls, data: dict):
        cls_instance = cls(
            account_id=ObjectId(data["account_id"]),
            file_name=data["file_name"],
            file_data=data["file_data"],
            file_type=FileType(data["file_type"]),
            pharmacy_id=data["pharmacy_id"],
            distributors=[DistributorTypes(distributor) for distributor in data["distributors"]],
            task_type=ScraperTaskActionType(data["task_type"]),
            date_created=data["date_created"],
            date_updated=data["date_updated"],
            report=data["report"],
            image_urls=data.get("image_urls")
        )
        cls_instance.id = data.get("_id") or data.get("id") or ""
        cls_instance.status = ScraperTaskItemStatus(
            status=TaskStatus(data["status"]["status"]),
            message=data["status"]["message"],
            progress=data["status"]["progress"],
            detailed_error_message=data["status"].get("detailed_error_message"),
        )
        return cls_instance
