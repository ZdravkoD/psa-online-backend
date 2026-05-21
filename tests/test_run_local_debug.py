import importlib.util
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace


MODULE_PATH = Path(__file__).resolve().parents[1] / "scraper" / "scripts" / "run_local_debug.py"
SPEC = importlib.util.spec_from_file_location("run_local_debug_module_for_tests", MODULE_PATH)
run_local_debug_module = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(run_local_debug_module)


class RunLocalDebugPayloadTests(unittest.TestCase):
    def test_build_local_task_payload_uses_blob_storage_url_for_input_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            input_file = Path(tmpdir) / "sample.xlsx"
            input_file.write_bytes(b"fake xlsx bytes")
            args = SimpleNamespace(
                input_json=None,
                input_file=input_file,
                product=None,
                quantity=1,
                pharmacy_id="2075077",
                distributors=["phoenix"],
                task_type="start_over",
            )

            payload = run_local_debug_module._build_local_task_payload(args)

        self.assertEqual(payload["file_name"], "sample.xlsx")
        self.assertEqual(payload["file_type"], "blob_storage_url")
        self.assertEqual(payload["file_data"], "https://local.test/input-files/sample.xlsx")

    def test_build_local_task_payload_rejects_conflicting_input_sources(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            input_file = Path(tmpdir) / "sample.xlsx"
            input_file.write_bytes(b"fake xlsx bytes")
            input_json = Path(tmpdir) / "sample.json"
            input_json.write_text('{"rows": []}', encoding="utf-8")
            args = SimpleNamespace(
                input_json=input_json,
                input_file=input_file,
                product=None,
                quantity=1,
                pharmacy_id="2075077",
                distributors=["phoenix"],
                task_type="start_over",
            )

            with self.assertRaisesRegex(SystemExit, "either --input-json or --input-file"):
                run_local_debug_module._build_local_task_payload(args)


class RunLocalDebugPatchingTests(unittest.TestCase):
    def test_patch_local_blob_clients_updates_task_handler_and_excel_worker_modules(self):
        task_handler_module = SimpleNamespace(AzureBlobClient="old-task-handler")
        excel_worker_module = SimpleNamespace(AzureBlobClient="old-excel-worker")
        modules = {
            "task_handler_module": task_handler_module,
            "excel_worker_module": excel_worker_module,
        }

        class FakeLocalAzureBlobClient:
            pass

        run_local_debug_module._patch_local_blob_clients(modules, FakeLocalAzureBlobClient)

        self.assertIs(task_handler_module.AzureBlobClient, FakeLocalAzureBlobClient)
        self.assertIs(excel_worker_module.AzureBlobClient, FakeLocalAzureBlobClient)

    def test_patch_local_cosmos_client_updates_task_handler_module(self):
        task_handler_module = SimpleNamespace(CosmosDbClient="old-cosmos")
        modules = {
            "task_handler_module": task_handler_module,
        }

        class FakeLocalCosmosDbClient:
            pass

        run_local_debug_module._patch_local_cosmos_client(modules, FakeLocalCosmosDbClient)

        self.assertIs(task_handler_module.CosmosDbClient, FakeLocalCosmosDbClient)


class RunLocalDebugCleanupTests(unittest.TestCase):
    def test_verify_cleanup_state_uses_scraper_hook(self):
        scraper = SimpleNamespace(
            get_name=lambda: "Phoenix",
            verify_cleanup_state=lambda: True,
        )

        result = run_local_debug_module._verify_cleanup_state(scraper)

        self.assertEqual(result, "verified Phoenix cleanup state")

    def test_verify_cleanup_state_raises_when_hook_reports_failure(self):
        scraper = SimpleNamespace(
            get_name=lambda: "Phoenix",
            verify_cleanup_state=lambda: False,
        )

        with self.assertRaisesRegex(ValueError, "cleanup verification failed"):
            run_local_debug_module._verify_cleanup_state(scraper)


if __name__ == "__main__":
    unittest.main()
