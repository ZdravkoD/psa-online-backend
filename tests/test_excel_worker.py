import sys
import types
import unittest
from pathlib import Path


SCRAPER_ROOT = Path(__file__).resolve().parents[1] / "scraper" / "scraper"
if str(SCRAPER_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRAPER_ROOT))


def ensure_module(name: str) -> types.ModuleType:
    module = sys.modules.get(name)
    if module is None:
        module = types.ModuleType(name)
        sys.modules[name] = module
    return module


openpyxl_module = ensure_module("openpyxl")
openpyxl_module.Workbook = type("Workbook", (), {})

openpyxl_styles_module = ensure_module("openpyxl.styles")
openpyxl_styles_module.Font = type("Font", (), {})

openpyxl_utils_module = ensure_module("openpyxl.utils")
openpyxl_utils_module.get_column_letter = lambda index: str(index)

openpyxl_worksheet_module = ensure_module("openpyxl.worksheet")
openpyxl_worksheet_worksheet_module = ensure_module("openpyxl.worksheet.worksheet")
openpyxl_worksheet_worksheet_module.Worksheet = type("Worksheet", (), {})
openpyxl_worksheet_module.worksheet = openpyxl_worksheet_worksheet_module

azure_blob_client_module = ensure_module("files.azure_blob_client")
azure_blob_client_module.AzureBlobClient = type("AzureBlobClient", (), {})

from files.excel_worker import ExcelWorker  # noqa: E402


class _FakeCell:
    def __init__(self, value, row):
        self.value = value
        self.row = row


class _FakeSheet:
    def __init__(self):
        self.iter_rows_calls = 0
        self.rows = [
            [_FakeCell(None, 1), _FakeCell("Product A", 1), _FakeCell(None, 1), _FakeCell(1, 1)],
            [_FakeCell(None, 2), _FakeCell("Product B", 2), _FakeCell(None, 2), _FakeCell(2, 2)],
        ]

    def iter_rows(self, **_kwargs):
        self.iter_rows_calls += 1
        return iter(self.rows)


class ExcelWorkerCachingTests(unittest.TestCase):
    def test_get_number_of_rows_is_cached(self):
        worker = ExcelWorker()
        fake_sheet = _FakeSheet()
        worker.inputSheet = fake_sheet

        self.assertEqual(worker.getNumberOfRows(), 2)
        self.assertEqual(worker.getNumberOfRows(), 2)
        self.assertEqual(fake_sheet.iter_rows_calls, 1)


if __name__ == "__main__":
    unittest.main()
