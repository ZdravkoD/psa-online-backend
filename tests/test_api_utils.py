import importlib.util
import os
import sys
import types
import unittest
from pathlib import Path
from unittest import mock


MODULE_PATH = Path(__file__).resolve().parents[1] / "azure-functions" / "api_utils.py"
SPEC = importlib.util.spec_from_file_location("api_utils", MODULE_PATH)
api_utils = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(api_utils)

CONFIG_MODULE_PATH = Path(__file__).resolve().parents[1] / "scraper" / "scraper" / "configuration" / "common.py"
CONFIG_SPEC = importlib.util.spec_from_file_location("scraper_configuration_common", CONFIG_MODULE_PATH)
config_common = importlib.util.module_from_spec(CONFIG_SPEC)
assert CONFIG_SPEC.loader is not None
dotenv_module = types.ModuleType("dotenv")
dotenv_module.load_dotenv = lambda *args, **kwargs: None
sys.modules.setdefault("dotenv", dotenv_module)
os.environ.setdefault("STING_CONFIG", "[]")
os.environ.setdefault("PHOENIX_CONFIG", "[]")
CONFIG_SPEC.loader.exec_module(config_common)


class BuildBlobObjectNameTests(unittest.TestCase):
    def test_build_blob_object_name_preserves_basename_only(self):
        with mock.patch.object(api_utils, "uuid4") as uuid4_mock:
            uuid4_mock.return_value.hex = "abc123"
            object_name = api_utils.build_blob_object_name("../unsafe/report.xlsx")

        self.assertEqual(object_name, "abc123_report.xlsx")

    def test_build_blob_object_name_rejects_empty_filename(self):
        with self.assertRaises(ValueError):
            api_utils.build_blob_object_name("")


class SecretRedactionTests(unittest.TestCase):
    def test_mask_secret_keeps_edges_only(self):
        self.assertEqual(config_common.mask_secret("supersecret"), "su*******et")

    def test_user_string_redacts_password(self):
        user = config_common.User(id="1", username="demo", password="topsecret")

        self.assertIn("to*****et", str(user))
        self.assertNotIn("topsecret", str(user))


if __name__ == "__main__":
    unittest.main()
