import json
import os
from datetime import datetime, timezone, timedelta
from typing import Optional, Tuple
import azure.functions as func
from azure.servicebus import ServiceBusClient, ServiceBusMessage
from azure.storage.blob import BlobServiceClient, BlobClient, ContainerClient
import logging

from bson import ObjectId
import jwt
from pubsub_client import AzureWebPubSubServiceClient
from werkzeug.utils import secure_filename

from cosmosdb_client import CosmosDbClient
from messaging import FileType, ScraperTaskActionType, ScraperTaskItem, ScraperTaskItemStatus, TaskStatus
from json_encoder import CustomJSONEncoder

app = func.FunctionApp()
cosmosDbClient = CosmosDbClient()
# Create a logger for this module
logger = logging.getLogger(__name__)
# Basic configuration for logging
logging.basicConfig(
    level=logging.DEBUG,
    format="[%(asctime)s][%(name)s][%(levelname)s]: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)


@app.route(route="task", auth_level=func.AuthLevel.ANONYMOUS, methods=["POST"])
def create_task(req: func.HttpRequest) -> func.HttpResponse:
    """
    This function accepts an excel file, selected pharmacy ID and distributors to use for scraping.
    It then creates the task in the CosmosDB and sends a message to the Service Bus queue for processing.

    Returns:
        func.HttpResponse:
            200: The ID of the created task.
            400: If the request is missing required parameters.
            500: If an error occurs.
    """
    logging.info('Python HTTP trigger function processed a request to create a task.')

    if req.form is None:
        return func.HttpResponse(
            "Please provide the required parameters in the request body.",
            status_code=400
        )

    content_type = req.headers.get('Content-Type')
    if not content_type:
        return func.HttpResponse(
            "Missing content type",
            status_code=400
        )
    if not content_type.startswith('multipart/form-data'):
        return func.HttpResponse(
            "Invalid content type",
            status_code=400
        )

    if req.form.get('json_content'):
        response = _create_task_json_content(req)
    else:
        response = _create_task_file_content(req)

    return response


def _create_task_json_content(req: func.HttpRequest) -> func.HttpResponse:
    """
    This function creates a task JSON object from the request body.

    Args:
        req (func.HttpRequest): The request object.

    Returns:
        dict: The task JSON object.
    """
    if req.form is None:
        return func.HttpResponse(
            "Please provide the required parameters in the request body.",
            status_code=400
        )
    json_content = req.form.get('json_content')
    if not json_content:
        return func.HttpResponse(
            "Please provide the json_content in the request body.",
            status_code=400
        )
    try:
        json_content = json.loads(json_content)
    except json.JSONDecodeError:
        return func.HttpResponse(
            "Invalid JSON content provided.",
            status_code=400
        )
    # TODO: enforce account_id when we start handling it
    _ = req.form.get('account_id')
    pharmacy_id = req.form.get('pharmacy_id')
    if not pharmacy_id:
        return func.HttpResponse(
            "Please provide the pharmacy_id in the request body.",
            status_code=400
        )
    distributors = json.loads(str(req.form.get('distributors')))
    if not distributors:
        return func.HttpResponse(
            "Please provide the distributors in the request body.",
            status_code=400
        )
    if not all(distributor in ["sting", "phoenix"] for distributor in distributors):
        return func.HttpResponse(
            "Invalid distributor names provided.",
            status_code=400
        )

    task_item = ScraperTaskItem(
        id=ObjectId(),
        account_id=ObjectId(),
        file_name="",
        file_data=json_content,
        file_type=FileType.JSON_CONTENT,
        pharmacy_id=pharmacy_id,
        distributors=distributors,
        task_type=ScraperTaskActionType.START_OVER,
        date_created=datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
        date_updated=datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
        status=ScraperTaskItemStatus(
            status=TaskStatus.IN_PROGRESS,
            message="Задачата стартира...",
            progress=0
        ),
        report=None
    )
    task_item.status = ScraperTaskItemStatus(
        status=TaskStatus.IN_PROGRESS,
        message="Задачата стартира...",
        progress=0
    )
    inserted_id = cosmosDbClient.create_item("tasks", task_item.to_insert_dict())
    task_item.id = inserted_id

    send_message_to_servicebus_queue(task_item.to_json())

    return func.HttpResponse(body=json.dumps({"id": str(task_item.id)}), status_code=201)


def _create_task_file_content(req: func.HttpRequest) -> func.HttpResponse:
    """
    This function creates a task JSON object from the request body.

    Args:
        req (func.HttpRequest): The request object.

    Returns:
        dict: The task JSON object.
    """
    if req.form is None:
        return func.HttpResponse(
            "Please provide the required parameters in the request body.",
            status_code=400
        )
    if req.files is None:
        return func.HttpResponse(
            "Please upload a file in the request body.",
            status_code=400
        )
    file = req.files.get('file')
    if not file:
        return func.HttpResponse(
            "Please upload a file in the request body.",
            status_code=400
        )
    filename = secure_filename(file.filename)
    filestream = file.stream
    filestream.seek(0)
    file_data = filestream.read()
    if filename == '':
        return func.HttpResponse(
            "Please upload a file with a valid name.",
            status_code=400
        )
    if not ('.' in filename and filename.rsplit('.', 1)[1].lower() in {'xlsx', 'xls', 'csv'}):
        return func.HttpResponse("Invalid file type", status_code=400)

    # TODO: enforce account_id when we start handling it
    _ = req.form.get('account_id')
    pharmacy_id = req.form.get('pharmacy_id')
    if not pharmacy_id:
        return func.HttpResponse(
            "Please provide the pharmacy_id in the request body.",
            status_code=400
        )
    distributors = json.loads(str(req.form.get('distributors')))
    if not distributors:
        return func.HttpResponse(
            "Please provide the distributors in the request body.",
            status_code=400
        )
    if not all(distributor in ["sting", "phoenix"] for distributor in distributors):
        return func.HttpResponse(
            "Invalid distributor names provided. Please provide 'sting' or 'phoenix' as distributor names.",
            status_code=400
        )

    # Upload file to Azure Blob Storage
    try:
        blob_storage_url = upload_file_bytes_to_blob_storage(filename, file_data)
    except Exception as e:
        logging.error(f"Failed to upload file to Blob Storage: {e}")
        return func.HttpResponse(
            f"Failed to upload file to Blob Storage. {e}",
            status_code=500
        )

    task_item = ScraperTaskItem(
        id=ObjectId(),
        account_id=ObjectId(),
        file_name=filename,
        file_data=blob_storage_url,
        file_type=FileType.BLOB_STORAGE_URL,
        pharmacy_id=pharmacy_id,
        distributors=distributors,
        task_type=ScraperTaskActionType.START_OVER,
        date_created=datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
        date_updated=datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
        status=ScraperTaskItemStatus(
            status=TaskStatus.IN_PROGRESS,
            message="Задачата стартира...",
            progress=0
        ),
        report=None
    )
    task_item.status = ScraperTaskItemStatus(
        status=TaskStatus.IN_PROGRESS,
        message="Задачата стартира...",
        progress=0
    )

    inserted_id = cosmosDbClient.create_item("tasks", task_item.to_insert_dict())
    task_item.id = inserted_id

    send_message_to_servicebus_queue(task_item.to_json())

    return func.HttpResponse(body=json.dumps({"id": str(task_item.id)}), status_code=201)


@app.route(route="task/{taskId}", auth_level=func.AuthLevel.ANONYMOUS, methods=["GET"])
def task(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Python HTTP trigger function processed a request to get a task.')

    task_id = req.route_params.get('taskId')
    if not task_id:
        return func.HttpResponse(
            "Please provide the task ID in the URI.",
            status_code=400
        )

    task = cosmosDbClient.read_item_by_id("tasks", task_id)
    if not task:
        return func.HttpResponse(
            "Task not found.",
            status_code=404
        )

    return func.HttpResponse(body=json.dumps(task, default=str), status_code=200, mimetype="application/json")


@app.route(route="tasks", auth_level=func.AuthLevel.ANONYMOUS, methods=["GET"])
def tasks(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Python HTTP trigger function processed a request to get all tasks.')

    try:
        filter, projection, sort, skip, limit = _tasks_parse_params(req=req)
    except ValueError as err:
        return func.HttpResponse(
            body=json.dumps({"error": str(err)}, cls=CustomJSONEncoder),
            status_code=400,
            mimetype="application/json")

    tasks = cosmosDbClient.read_items(collection_name="tasks", filter=filter, projection=projection, sort=sort, skip=skip, limit=limit)

    return func.HttpResponse(body=json.dumps(tasks, cls=CustomJSONEncoder), status_code=200, mimetype="application/json")


def _tasks_parse_params(req: func.HttpRequest) -> Tuple[Optional[dict], Optional[dict], Optional[dict], Optional[int], Optional[int]]:
    # Parse filter param
    filter_param = req.params.get("filter", None)
    filter_dict = parse_json_param(filter_param, "filter")

    # Parse projection param
    projection_param = req.params.get("projection", None)
    projection_dict = parse_json_param(projection_param, "projection")

    # Parse sort param
    sort_param = req.params.get("sort", None)
    sort_dict = parse_json_param(sort_param, "sort")

    # Parse skip param (integer)
    skip_param = req.params.get("skip", None)
    skip = parse_int_param(skip_param, "skip")

    # Parse limit param (integer)
    limit_param = req.params.get("limit", None)
    limit = parse_int_param(limit_param, "limit")

    return filter_dict, projection_dict, sort_dict, skip, limit


@app.route(route="pharmacies", auth_level=func.AuthLevel.ANONYMOUS, methods=["GET"])
def get_pharmacies(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Python HTTP trigger function processed a request to get all pharmacies.')

    tasks = cosmosDbClient.read_items(collection_name="pharmacies")

    return func.HttpResponse(body=json.dumps(tasks), status_code=200, mimetype="application/json")


@app.route(route="distributors", auth_level=func.AuthLevel.ANONYMOUS, methods=["GET"])
def get_distributors(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Python HTTP trigger function processed a request to get all distributors.')

    tasks = cosmosDbClient.read_items(collection_name="distributors")

    return func.HttpResponse(body=json.dumps(tasks), status_code=200, mimetype="application/json")


def upload_file_bytes_to_blob_storage(filename: str, file_data: bytes):
    connection_string = os.getenv("AZURE_BLOB_STORAGE_CONNECTION_STRING", "")
    logger.info(f"connection_string {connection_string}")
    container_name = os.getenv("AZURE_BLOB_STORAGE_INPUT_FILES_CONTAINER_NAME", "")
    logger.info(f"container_name {container_name}")
    blob_service_client = BlobServiceClient.from_connection_string(connection_string)
    container_client: ContainerClient = blob_service_client.get_container_client(container_name)
    blob_client: BlobClient = container_client.get_blob_client(filename)
    blob_client.upload_blob(file_data, overwrite=True)
    return blob_client.url


@app.route(route="pubsub-token", auth_level=func.AuthLevel.ANONYMOUS, methods=["GET"])
def pubsub_token(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Python HTTP trigger function processed a request for PubSub token.')
    hub_name = req.params.get('hub_name')
    user_id = req.params.get('user_id')

    service_key = os.getenv("AZURE_WEB_PUBSUB_ACCESS_KEY", "")

    if not hub_name or not user_id:
        return func.HttpResponse(
            "Please provide hub_name and user_id in the query string.",
            status_code=400
        )
    if not service_key:
        return func.HttpResponse(
            "The service key is not set.",
            status_code=500
        )

    endpoint = f"{os.getenv('AZURE_WEB_PUBSUB_ENDPOINT', '')}/client/hubs/{hub_name}"
    issuer = f"{endpoint}/"
    audience = f"{endpoint}/"

    # Calculate the expiration time
    expiration_time = datetime.utcnow() + timedelta(minutes=60)

    # Generate the token
    token = jwt.encode({
        'aud': audience,
        'iss': issuer,
        'sub': user_id,
        'exp': expiration_time
    }, service_key, algorithm='HS256')

    return func.HttpResponse(body=token, status_code=200)


# TODO: DO not deploy this function to production. It is fo test only
@app.route(route="pub-task-update", auth_level=func.AuthLevel.ANONYMOUS, methods=["POST"])
def pub_task_update(req: func.HttpRequest) -> func.HttpResponse:
    # get POST body into JSON
    req_body = req.get_json()
    AzureWebPubSubServiceClient().send_task_update_to_all(req_body)

    return func.HttpResponse(body="Sent update to queue", status_code=200)


def send_message_to_servicebus_queue(message: dict):
    CONNECTION_STR = os.getenv("psaonline_SERVICEBUS", "")
    QUEUE_NAME = os.getenv("psaonline_SERVICEBUS_QUEUE", "")
    servicebus_client = ServiceBusClient.from_connection_string(conn_str=CONNECTION_STR, logging_enable=True)
    with servicebus_client:
        sender = servicebus_client.get_queue_sender(queue_name=QUEUE_NAME)
        with sender:
            sb_message = ServiceBusMessage(json.dumps(message), content_type="application/json")
            sender.send_messages(sb_message)
            logging.info(f"Sent message to the Service Bus queue ({QUEUE_NAME}): {message}")


@app.route(route="input-file/{filename}", auth_level=func.AuthLevel.ANONYMOUS, methods=["GET"])
def get_input_file(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Python HTTP trigger function processed a request to get an input file.')

    filename = req.route_params.get('filename')
    if not filename:
        return func.HttpResponse(
            "Please provide the filename in the URI.",
            status_code=400
        )

    connection_string = os.getenv("AZURE_BLOB_STORAGE_CONNECTION_STRING", "")
    container_name = os.getenv("AZURE_BLOB_STORAGE_INPUT_FILES_CONTAINER_NAME", "")
    blob_service_client = BlobServiceClient.from_connection_string(connection_string)
    container_client: ContainerClient = blob_service_client.get_container_client(container_name)
    blob_client: BlobClient = container_client.get_blob_client(filename)

    try:
        blob_data = blob_client.download_blob().readall()
    except Exception as e:
        logging.error(f"Failed to download file from Blob Storage: {e}")
        return func.HttpResponse(
            "File not found.",
            status_code=404
        )

    # return func.HttpResponse(body=blob_data, status_code=200, mimetype="application/octet-stream")
    return func.HttpResponse(body=blob_data, status_code=200, mimetype="application/octet-stream", headers={
        "Content-Disposition": f"attachment; filename={filename}"
    })


@app.service_bus_queue_trigger(arg_name="msg", queue_name=os.getenv("psaonline_SERVICEBUS_QUEUE_TASK_UPDATES", "task-updates"), connection="psaonline_SERVICEBUS")
def servicebus_trigger__task_updates(msg: func.ServiceBusMessage):
    """
    Example message body:
    {
        "account_id": "123",
        "task_id": "123",
        "status": "in progress",
        "message": "Задачата стартира...",
        "progress": "37"
    }
    """
    logging.info(f'Received Service Bus message for task update: {msg.get_body().decode()}')
    msg_dict = json.loads(msg.get_body().decode())
    msg_object = ScraperTaskItem.from_dict(msg_dict)
    task_id: str = str(msg_object.id)

    task: ScraperTaskItem = ScraperTaskItem.from_dict(cosmosDbClient.read_item_by_id("tasks", task_id) or {})
    task.date_updated = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    task.status = msg_object.status
    task.report = msg_object.report
    task.image_urls = msg_object.image_urls
    cosmosDbClient.update_item("tasks", task.id, task.to_insert_dict())

    AzureWebPubSubServiceClient().send_task_update_to_all(msg_dict)


def parse_json_param(param_value: Optional[str], param_name: str) -> Optional[dict]:
    """Helper function to parse a JSON string parameter."""
    if not param_value or param_value.strip() == "":
        return None
    try:
        return json.loads(param_value)
    except json.JSONDecodeError:
        raise ValueError(f"Invalid JSON in {param_name} parameter")


def parse_int_param(param_value: Optional[str], param_name: str) -> Optional[int]:
    """Helper function to parse an integer parameter."""
    if not param_value or param_value.strip() == "":
        return None
    try:
        return int(param_value)
    except ValueError:
        raise ValueError(f"Invalid integer in {param_name} parameter")
