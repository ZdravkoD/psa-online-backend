import datetime
import json
import os
import azure.functions as func
from azure.servicebus import ServiceBusClient, ServiceBusMessage
from azure.storage.blob import BlobServiceClient, BlobClient, ContainerClient
import logging

from bson import ObjectId
import jwt
from pubsub_client import AzureWebPubSubServiceClient
from werkzeug.utils import secure_filename

from cosmosdb_client import CosmosDbClient
from messaging import FileType, ScraperTaskActionType, ScraperTaskItem, ScraperTaskUpdates, TaskStatus
from json_encoder import CustomJSONEncoder

app = func.FunctionApp()


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
        account_id=ObjectId(),
        file_name="",
        file_data=json_content,
        file_type=FileType.JSON_CONTENT,
        pharmacy_id=pharmacy_id,
        distributors=distributors,
        task_type=ScraperTaskActionType.START_OVER
    )
    cosmosDbClient = CosmosDbClient()
    inserted_id = cosmosDbClient.create_item("tasks", task_item.to_json())
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
        account_id=ObjectId(),
        file_name=filename,
        file_data=blob_storage_url,
        file_type=FileType.BLOB_STORAGE_URL,
        pharmacy_id=pharmacy_id,
        distributors=distributors,
        task_type=ScraperTaskActionType.START_OVER
    )

    cosmosDbClient = CosmosDbClient()
    inserted_id = cosmosDbClient.create_item("tasks", task_item.to_json())
    task_item.id = inserted_id

    send_message_to_servicebus_queue(task_item.to_json())

    return func.HttpResponse(body=json.dumps({"id": str(task_item.id)}), status_code=201)


@app.route(route="task", auth_level=func.AuthLevel.ANONYMOUS, methods=["GET"])
def task(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Python HTTP trigger function processed a request to get a task.')

    task_id = req.params.get('id')
    if not task_id:
        return func.HttpResponse(
            "Please provide the task ID in the query string.",
            status_code=400
        )

    cosmosDbClient = CosmosDbClient()
    task = cosmosDbClient.read_item_by_id("tasks", task_id)
    if not task:
        return func.HttpResponse(
            "Task not found.",
            status_code=404
        )

    return func.HttpResponse(body=json.dumps(task), status_code=200, mimetype="application/json")


@app.route(route="tasks", auth_level=func.AuthLevel.ANONYMOUS, methods=["GET"])
def tasks(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Python HTTP trigger function processed a request to get all tasks.')

    cosmosDbClient = CosmosDbClient()
    tasks = cosmosDbClient.read_items("tasks", {})

    return func.HttpResponse(body=json.dumps(tasks, cls=CustomJSONEncoder), status_code=200, mimetype="application/json")


@app.route(route="pharmacies", auth_level=func.AuthLevel.ANONYMOUS, methods=["GET"])
def get_pharmacies(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Python HTTP trigger function processed a request to get all pharmacies.')

    cosmosDbClient = CosmosDbClient()
    tasks = cosmosDbClient.read_items("pharmacies", {})

    return func.HttpResponse(body=json.dumps(tasks), status_code=200, mimetype="application/json")


@app.route(route="distributors", auth_level=func.AuthLevel.ANONYMOUS, methods=["GET"])
def get_distributors(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Python HTTP trigger function processed a request to get all distributors.')

    cosmosDbClient = CosmosDbClient()
    tasks = cosmosDbClient.read_items("distributors", {})

    return func.HttpResponse(body=json.dumps(tasks), status_code=200, mimetype="application/json")


def upload_file_bytes_to_blob_storage(filename: str, file_data: bytes):
    connection_string = os.getenv("AZURE_BLOB_STORAGE_CONNECTION_STRING", "")
    print("connection_string", connection_string)
    container_name = os.getenv("AZURE_BLOB_STORAGE_INPUT_FILES_CONTAINER_NAME", "")
    print("container_name", container_name)
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

    endpoint = f"https://psa-pubsub.webpubsub.azure.com/client/hubs/{hub_name}"
    issuer = f"{endpoint}/"
    audience = f"{endpoint}/"

    # Calculate the expiration time
    expiration_time = datetime.datetime.utcnow() + datetime.timedelta(minutes=60)

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
            logging.info(f"Sent message to the Service Bus queue: {message}")


@app.service_bus_queue_trigger(arg_name="msg", queue_name="task-updates", connection="psaonline_SERVICEBUS")
def servicebus_trigger__task_updates(msg: func.ServiceBusMessage):
    """
    Example message body:
    {
        "account_id": "123",
        "task_id": "123",
        "status": "in progress",
        "message": "Starting the task...",
        "progress": "37"
    }
    """
    logging.info(f'Received Service Bus message for task update: {msg.get_body().decode()}')
    msg_object: dict = json.loads(msg.get_body().decode())

    print("ULALA:", json.dumps(msg_object))
    cosmosDbClient = CosmosDbClient()
    task: ScraperTaskItem = ScraperTaskItem.from_dict(cosmosDbClient.read_item_by_id("tasks", msg_object.get("task_id")) or {})
    print("DANET:", json.dumps(task.to_json()))
    if msg_object.get("status") == TaskStatus.FINAL_REPORT:
        task.report = msg_object.get("report", {})
    else:
        task.status = ScraperTaskUpdates(
            account_id=task.account_id,
            task_id=task.id,
            status=str(msg_object.get("status")) if msg_object.get("status") else TaskStatus.IN_PROGRESS,
            message=str(msg_object.get("message")),
            progress=int(msg_object.get("progress") or 0)
        )
    cosmosDbClient.update_item("tasks", task.id, task.to_update_dict())

    AzureWebPubSubServiceClient().send_task_update_to_all(json.loads(msg.get_body().decode()))
