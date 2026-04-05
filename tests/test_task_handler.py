import importlib.util
import sys
import types
import unittest
from pathlib import Path
from unittest import mock


def ensure_module(name: str) -> types.ModuleType:
    module = sys.modules.get(name)
    if module is None:
        module = types.ModuleType(name)
        sys.modules[name] = module
    return module


ensure_module("dal")
dal_cosmos_module = ensure_module("dal.cosmosdb_client")
dal_cosmos_module.CosmosDbClient = type("CosmosDbClient", (), {})

ensure_module("pharmacy_distributors")
ensure_module("pharmacy_distributors.common")
common_models_module = ensure_module("pharmacy_distributors.common.models")
common_models_module.ScrapedProductInfo = type("ScrapedProductInfo", (), {})
browser_common_module = ensure_module("pharmacy_distributors.common.browser_common")
browser_common_module.BrowserCommon = type("BrowserCommon", (), {})

ensure_module("pharmacy_distributors.sting")
sting_module = ensure_module("pharmacy_distributors.sting.sting")
sting_module.StingPharma = type("StingPharma", (), {})

ensure_module("pharmacy_distributors.phoenix")
phoenix_module = ensure_module("pharmacy_distributors.phoenix.phoenix_optimized")
phoenix_module.PhoenixPharmaOptimized = type("PhoenixPharmaOptimized", (), {})

ensure_module("selenium")
ensure_module("selenium.common")
selenium_exceptions_module = ensure_module("selenium.common.exceptions")
selenium_exceptions_module.StaleElementReferenceException = type("StaleElementReferenceException", (Exception,), {})

ensure_module("messaging")
messaging_module = ensure_module("messaging.messaging")
messaging_module.ScraperTaskItem = type("ScraperTaskItem", (), {})

ensure_module("files")
file_worker_module = ensure_module("files.file_worker")
file_worker_module.FileWorker = type("FileWorker", (), {})
file_worker_module.RowInfo = type("RowInfo", (), {})
file_worker_factory_module = ensure_module("files.file_worker_factory")


class _StubFactory:
    def __init__(self, *_args, **_kwargs):
        pass

    def get_file_worker(self):
        return object()


file_worker_factory_module.FileWorkerFactory = _StubFactory
azure_blob_module = ensure_module("files.azure_blob_client")
azure_blob_module.AzureBlobClient = type("AzureBlobClient", (), {})

ensure_module("task_handler")
task_update_publisher_module = ensure_module("task_handler.task_update_publisher")
task_update_publisher_module.TaskUpdatePublisher = type("TaskUpdatePublisher", (), {})

ensure_module("psa_logger")
psa_logger_module = ensure_module("psa_logger.logger")
psa_logger_module.get_current_logfile_name = lambda: "log.txt"
psa_logger_module.get_current_logfile_data = lambda: b"log-data"


MODULE_PATH = Path(__file__).resolve().parents[1] / "scraper" / "scraper" / "task_handler" / "task_handler.py"
SPEC = importlib.util.spec_from_file_location("task_handler_module", MODULE_PATH)
task_handler_module = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(task_handler_module)


class TaskHandlerInitTests(unittest.TestCase):
    def test_init_reraises_original_error_when_publisher_creation_fails(self):
        fake_task = types.SimpleNamespace(file_type="json_content")

        with mock.patch.object(task_handler_module, "TaskUpdatePublisher", side_effect=RuntimeError("publisher boom")):
            with self.assertRaisesRegex(RuntimeError, "publisher boom"):
                task_handler_module.TaskHandler(fake_task)


class TaskHandlerErrorDetailsTests(unittest.TestCase):
    def test_build_task_error_details_includes_scraper_context(self):
        scraper = mock.Mock()
        scraper.format_debug_context.return_value = "\n".join([
            "Scraper: Sting",
            "Current action: Selecting Sting payment channel",
            "Page title: Избор на канал",
            "Current URL: http://example.test/page",
        ])

        result = task_handler_module.build_task_error_details(RuntimeError("timeout from aborted by navigation"), [scraper])

        self.assertIn("Message: timeout from aborted by navigation", result)
        self.assertIn("Current action: Selecting Sting payment channel", result)
        self.assertIn("Current URL: http://example.test/page", result)

    def test_build_task_error_summary_uses_scraper_action_and_reason(self):
        scraper = mock.Mock()
        scraper.get_name.return_value = "Phoenix"
        scraper.current_action = "Adding product to Phoenix cart"

        result = task_handler_module.build_task_error_summary(
            RuntimeError("Phoenix: element click intercepted"),
            [scraper],
        )

        self.assertEqual(
            result,
            "Phoenix - Изпълнение на задачата: стъпка 'Adding product to Phoenix cart' се провали, защото елементът не може да бъде кликнат, защото друг елемент го покрива."
        )

    def test_build_task_error_summary_uses_explicit_stage_and_operation(self):
        result = task_handler_module.build_task_error_summary(
            ValueError("The JSON content is not valid"),
            [],
            stage="Валидиране на входния файл",
            operation="orders.json",
        )

        self.assertEqual(
            result,
            "Валидиране на входния файл: стъпка 'orders.json' се провали, защото JSON съдържанието не е валидно."
        )


if __name__ == "__main__":
    unittest.main()
