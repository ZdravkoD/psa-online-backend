from azure.cosmos import CosmosClient, exceptions
from azure.cosmos.database import DatabaseProxy
import threading


# TODO: Implement the below template
class CosmosDbClient:
    _instance = None
    _lock = threading.Lock()
    client = None
    database: DatabaseProxy

    # Singleton pattern implementation
    def __new__(cls, *args, **kwargs):
        with cls._lock:
            if not cls._instance:
                cls._instance = super(CosmosDbClient, cls).__new__(cls)
                # Initialize the client here
                endpoint = "YOUR_COSMOS_DB_ENDPOINT"
                key = "YOUR_COSMOS_DB_KEY"
                cls._instance.client = CosmosClient(endpoint, key)
                cls._instance.database = cls._instance.client.get_database_client("YOUR_DATABASE_NAME")
            return cls._instance

    def read_items(self, collection_name, query):
        container = self.database.get_container_client(collection_name)
        items = list(container.query_items(query=query, enable_cross_partition_query=True))
        return items

    def create_item(self, collection_name, document):
        container = self.database.get_container_client(collection_name)
        response = container.create_item(body=document)
        return response

    def update_item(self, collection_name, item_id, document):
        container = self.database.get_container_client(collection_name)
        try:
            read_item = container.read_item(item=item_id, partition_key=document['partition_key'])
            for key in document:
                read_item[key] = document[key]
            response = container.replace_item(item=read_item, body=read_item)
            return response
        except exceptions.CosmosResourceNotFoundError:
            return "Item not found"

    def delete_item(self, collection_name, item_id, partition_key):
        container = self.database.get_container_client(collection_name)
        response = container.delete_item(item=item_id, partition_key=partition_key)
        return response

# Usage Example
# if __name__ == "__main__":
#     client = CosmosDbClient()
#     new_document = {"id": "001", "content": "Hello Cosmos DB", "partition_key": "001"}
#     print(client.create_item("YourCollectionName", new_document))
#     print(client.read_items("YourCollectionName", "SELECT * FROM c"))
#     print(client.update_item("YourCollectionName", "001", {"content": "Hello updated Cosmos DB"}))
#     print(client.delete_item("YourCollectionName", "001", "001"))
