from files.excel_worker import ExcelWorker
from files.file_worker import FileWorker
from files.json_content_worker import JsonContentWorker
from shared_lib.messaging.messaging import FileType


class FileWorkerFactory:
    def __init__(self, file_type: FileType):
        self.file_type = file_type

    def get_file_worker(self) -> FileWorker:
        if self.file_type == FileType.BLOB_STORAGE_URL:
            return ExcelWorker()
        elif self.file_type == FileType.JSON_CONTENT:
            return JsonContentWorker()
        else:
            raise ValueError(f'Unsupported file format: {self.file_type}')
