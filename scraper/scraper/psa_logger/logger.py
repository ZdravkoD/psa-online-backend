import logging
from datetime import datetime


def setup_logging():
    # Basic configuration for logging
    logging.basicConfig(
        level=logging.DEBUG,
        format="[%(asctime)s.%(msecs)03d][%(name)s][%(levelname)s]: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        encoding="utf-8",
    )

    # Set a higher log level for azure servicebus library
    logging.getLogger("azure.servicebus").setLevel(logging.WARNING)
    logging.getLogger("selenium.webdriver").setLevel(logging.WARNING)
    logging.getLogger("urllib3.connectionpool").setLevel(logging.WARNING)
    logging.getLogger("azure.core.pipeline.policies.http_logging_policy").setLevel(logging.WARNING)
    logging.getLogger("files.azure_blob_client").setLevel(logging.WARNING)

    # Example of adding a custom handler
    current_date = datetime.now().strftime("%Y-%m-%d")
    file_handler = logging.FileHandler(f'app_{current_date}.log')
    file_handler.setLevel(logging.INFO)
    file_format = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    file_handler.setFormatter(file_format)

    # Add the handler to the root logger
    logging.getLogger().addHandler(file_handler)


def get_current_logfile_name():
    for handler in logging.getLogger().handlers:
        if isinstance(handler, logging.FileHandler):
            return handler.baseFilename.split('/')[-1]
    return None


def get_current_logfile_data():
    for handler in logging.getLogger().handlers:
        if isinstance(handler, logging.FileHandler):
            with open(handler.baseFilename, "r") as f:
                return f.read()
    return None
