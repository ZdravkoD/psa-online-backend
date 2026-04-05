import importlib.util
import unittest
from pathlib import Path
from unittest import mock


MODULE_PATH = Path(__file__).resolve().parents[1] / "azure-functions" / "api_utils.py"
SPEC = importlib.util.spec_from_file_location("api_utils", MODULE_PATH)
api_utils = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(api_utils)


class BuildBlobObjectNameTests(unittest.TestCase):
    def test_build_blob_object_name_preserves_basename_only(self):
        with mock.patch.object(api_utils, "uuid4") as uuid4_mock:
            uuid4_mock.return_value.hex = "abc123"
            object_name = api_utils.build_blob_object_name("../unsafe/report.xlsx")

        self.assertEqual(object_name, "abc123_report.xlsx")

    def test_build_blob_object_name_rejects_empty_filename(self):
        with self.assertRaises(ValueError):
            api_utils.build_blob_object_name("")


if __name__ == "__main__":
    unittest.main()
