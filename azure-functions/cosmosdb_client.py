import os
from bson import ObjectId
from pymongo import MongoClient
import threading


class CosmosDbClient:
    _instance = None
    _lock = threading.Lock()
    database = None

    def __new__(cls, *args, **kwargs):
        print("CosmosDbClient::__new__() called to create")
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    print("Creating CosmosDbClient instance")
                    cls._instance = super(CosmosDbClient, cls).__new__(cls)
                    cls._instance._initialize_client()
        return cls._instance

    def _initialize_client(self):
        # Initialize the client here
        print("Initializing CosmosDbClient")
        connection_string = os.getenv("AZURE_COSMOS_DB_CONNECTION_STRING", "")
        self.client = MongoClient(connection_string)
        self.database = self.client.get_database("psa")

    def read_items(self, collection_name: str, query: dict):
        if self.database is None:
            raise ValueError("Database is not initialized")
        collection = self.database[collection_name]
        items = list(collection.find(query))
        for item in items:
            if item.get("_id"):
                item["id"] = str(item["_id"])
                item.pop("_id")
        return items

    def read_item_by_id(self, collection_name, id):
        if self.database is None:
            raise ValueError("Database is not initialized")
        collection = self.database[collection_name]
        item = collection.find_one(ObjectId(id))
        if item and item.get("_id"):
            item["id"] = str(item["_id"])
            item.pop("_id")

        return item

    def create_item(self, collection_name, document):
        if self.database is None:
            raise ValueError("Database is not initialized")
        collection = self.database[collection_name]
        response = collection.insert_one(document)
        return response.inserted_id

    def update_item(self, collection_name, item_id, document):
        if self.database is None:
            raise ValueError("Database is not initialized")
        collection = self.database[collection_name]
        response = collection.update_one({"_id": ObjectId(item_id)}, {"$set": document})
        return response.modified_count

    def delete_item(self, collection_name, item_id):
        if self.database is None:
            raise ValueError("Database is not initialized")
        collection = self.database[collection_name]
        response = collection.delete_one({"_id": ObjectId(item_id)})
        return response.deleted_count
