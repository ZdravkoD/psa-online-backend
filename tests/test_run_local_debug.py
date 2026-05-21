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


if __name__ == "__main__":
    unittest.main()
