from azure.storage.blob import BlobServiceClient

from configuration.common import AzureConfig


class AzureBlobClient:
    def __init__(self):
        self.connection_string = AzureConfig.BlobStorage.CONNECTION_STRING
        self.input_container_name = AzureConfig.BlobStorage.INPUT_FILES_CONTAINER_NAME
        self.output_container_name = AzureConfig.BlobStorage.OUTPUT_FILES_CONTAINER_NAME

        self.blob_service_client = BlobServiceClient.from_connection_string(self.connection_string)

    def _get_blob_client(self, container_name, blob_name):
        container_client = self.blob_service_client.get_container_client(container_name)
        return container_client.get_blob_client(blob_name)

    def upload_blob_to_output_container(self, blob_name, data):
        print(f"Uploading blob {blob_name} to container {self.output_container_name} with size {len(data)} bytes")
        blob_client = self._get_blob_client(self.output_container_name, blob_name)
        blob_client.upload_blob(data, overwrite=True)

    def download_blob_from_input_container(self, blob_name: str):
        print(f"Downloading blob {blob_name} from container {self.input_container_name}")
        blob_client = self._get_blob_client(self.input_container_name, blob_name)
        return blob_client.download_blob().readall()
