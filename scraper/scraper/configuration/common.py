import json
import os
from typing import List, Union
from dotenv import load_dotenv

from psa_logger.logger import get_logger


logger = get_logger(__name__)

load_dotenv(override=True)


def get_variable(
    env_variable_name, file_variable_name, path_to_json_file, default_value=None
) -> str:
    try:
        with open(path_to_json_file, "r", encoding="utf-8") as f:
            data = json.loads(f.read())
        return data[file_variable_name]
    except Exception:
        value = os.getenv(env_variable_name)
        if value is None:
            if default_value is None:
                logger.warning(
                    f"Environment variable {env_variable_name} or {file_variable_name} not set"
                )
                return ""
            return default_value

        return value


def get_variable_bool(
    env_variable_name, file_variable_name, path_to_json_file, default_value=None
) -> bool:
    try:
        with open(path_to_json_file, "r", encoding="utf-8") as f:
            data = json.loads(f.read())
        return data[file_variable_name]
    except Exception:
        value = os.getenv(env_variable_name)
        if value is None:
            if default_value is not None:
                return default_value
            logger.warning(
                f"Environment variable {env_variable_name} or {file_variable_name} not set"
            )
            return False

        return str.lower(value) == "true" or value == "1"


class AzureConfig:
    class ServiceBusTasks:
        CONNECTION_STRING = get_variable(
            "AZURE_SERVICE_BUS_CONNECTION_STRING",
            "connection_string",
            "azure-config.json",
        )
        QUEUE_NAME = get_variable(
            "AZURE_SERVICE_BUS_QUEUE_NAME", "queue_name", "azure-config.json"
        )

    class ServiceBusTasksUpdates:
        CONNECTION_STRING = get_variable(
            "AZURE_SERVICE_BUS_CONNECTION_STRING",
            "connection_string",
            "azure-config.json",
        )
        QUEUE_NAME = get_variable(
            "AZURE_SERVICE_BUS_TASK_UPDATES_QUEUE_NAME", "queue_name", "azure-config.json"
        )

    class BlobStorage:
        CONNECTION_STRING = get_variable(
            "AZURE_BLOB_STORAGE_CONNECTION_STRING",
            "connection_string",
            "azure-config.json",
        )
        INPUT_FILES_CONTAINER_NAME = get_variable(
            "AZURE_BLOB_STORAGE_INPUT_FILES_CONTAINER_NAME",
            "input_files_container_name",
            "azure-config.json",
        )
        OUTPUT_FILES_CONTAINER_NAME = get_variable(
            "AZURE_BLOB_STORAGE_OUTPUT_FILES_CONTAINER_NAME",
            "output_files_container_name",
            "azure-config.json",
        )


class User:
    def __init__(self, id: str, username: str, password: str):
        self.id = id
        self.username = username
        self.password = password

    def __str__(self):
        return f"User(id={self.id}, username={self.username}, password={self.password})"


class UserList:
    def __init__(self, json_data: Union[str, List[dict]]):
        self.users: List[User] = []
        self.load_users(json_data)

    def load_users(self, json_data: Union[str, List[dict]]):
        print("Loading users from JSON data:", json_data, "Type:", type(json_data))
        # Load user data from JSON, which is a string in JSON format
        # Check if json_data is a string, if so, parse it to JSON
        while isinstance(json_data, str):
            json_data = json.loads(json_data)

        user_data = json_data

        print("user_data:", user_data, "Type:", type(user_data))

        for user_dict in user_data:
            user = User(id=user_dict['id'], username=user_dict['username'], password=user_dict['password'])
            self.users.append(user)

        print(f"Loaded {len(self.users)} users from JSON data: ", self.users[0])

    def get_user(self, username):
        # Retrieve a user by username
        for user in self.users:
            if user.username == username:
                return user
        return None

    def get_all_users(self):
        return self.users


class DistributorConfig:
    class Sting:
        CONFIG: UserList = UserList(get_variable("STING_CONFIG", "sting", "distributor-config.json"))

    class Phoenix:
        CONFIG: UserList = UserList(get_variable("PHOENIX_CONFIG", "phoenix", "distributor-config.json"))

    INIT_CONFIG_FROM = get_variable(
        "INIT_CONFIG_FROM", "init_config_from", "distributor-config.json", "env"
    )
    COSMOS_DB_CONNECTION_STRING = get_variable(
        "AZURE_COSMOS_DB_CONNECTION_STRING", "connection_string", "distributor-config.json"
    )
    COSMOS_DB_PRIMARY_KEY = get_variable(
        "COSMOS_DB_PRIMARY_KEY", "primary_key", "distributor-config.json"
    )
    COSMOS_DB_DATABASE_NAME = get_variable(
        "COSMOS_DB_DATABASE_NAME", "database_name", "distributor-config.json"
    )

    def __init__(self):
        print("Initializing DistributorConfig")
        if self.INIT_CONFIG_FROM == "db":
            self._init_from_db()

    def _init_from_db(self):
        """
        Init config from CosmosDB collection "Distributor_config"
        """
        # TODO: Implement this via CosmosDbClient
        # # Initialize the Cosmos client
        # client = CosmosClient(self.COSMOS_DB_CONNECTION_STRING, credential=self.COSMOS_DB_PRIMARY_KEY)

        # # Connect to the database and container
        # database = client.get_database_client(self.COSMOS_DB_DATABASE_NAME)
        # container = database.get_container_client('distributor_config')

        # # Query these items using SQL query
        # query = "SELECT * FROM c"
        # items = list(container.query_items(
        #     query=query,
        # ))

        # # Print the items
        # for item in items:
        #     print(item)
