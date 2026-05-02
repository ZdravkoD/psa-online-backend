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


ensure_module("pharmacy_distributors")
ensure_module("pharmacy_distributors.common")
models_module = ensure_module("pharmacy_distributors.common.models")
models_module.ScrapedProductInfo = type("ScrapedProductInfo", (), {})
ensure_module("requests")
xmltodict_module = ensure_module("xmltodict")
xmltodict_module.parse = lambda *_args, **_kwargs: {"dataset": {}}

phoenix_pkg = ensure_module("pharmacy_distributors.phoenix")
phoenix_module_stub = ensure_module("pharmacy_distributors.phoenix.phoenix")


class StubPhoenixPharma:
    def add_product_to_cart(self, quantity):
        return quantity is not None


phoenix_module_stub.PhoenixPharma = StubPhoenixPharma
phoenix_pkg.phoenix = phoenix_module_stub


MODULE_PATH = Path(__file__).resolve().parents[1] / "scraper" / "scraper" / "pharmacy_distributors" / "phoenix" / "phoenix_optimized.py"
SPEC = importlib.util.spec_from_file_location("phoenix_optimized_module_for_tests", MODULE_PATH)
phoenix_optimized_module = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(phoenix_optimized_module)


class PhoenixOptimizedPayloadTests(unittest.TestCase):
    def test_decode_order_item_rows_returns_list_for_single_row_xml(self):
        phoenix = phoenix_optimized_module.PhoenixPharmaOptimized.__new__(phoenix_optimized_module.PhoenixPharmaOptimized)
        encoded_xml = (
            "&lt;?xml version=&quot;1.0&quot; encoding=&quot;UTF-8&quot; standalone=&quot;yes&quot;?&gt;"
            "&lt;dataset&gt;&lt;row&gt;&lt;article_id&gt;5344&lt;/article_id&gt;&lt;quantity&gt;2&lt;/quantity&gt;&lt;/row&gt;&lt;/dataset&gt;"
        )
        original_parse = phoenix_optimized_module.xmltodict.parse
        phoenix_optimized_module.xmltodict.parse = lambda *_args, **_kwargs: {
            "dataset": {"row": {"article_id": "5344", "quantity": "2"}}
        }
        try:
            rows = phoenix._decode_order_item_rows(encoded_xml)
        finally:
            phoenix_optimized_module.xmltodict.parse = original_parse

        self.assertEqual(rows, [{"article_id": "5344", "quantity": "2"}])

    def test_build_commit_payload_includes_totals_and_item_xml(self):
        phoenix = phoenix_optimized_module.PhoenixPharmaOptimized.__new__(phoenix_optimized_module.PhoenixPharmaOptimized)
        phoenix._xml_safe = phoenix_optimized_module.PhoenixPharmaOptimized._xml_safe.__get__(phoenix)
        phoenix._encode_order_items_xml = phoenix_optimized_module.PhoenixPharmaOptimized._encode_order_items_xml.__get__(phoenix)

        order_row = {
            "order_id": "15580946",
            "order_type": "F",
            "order_state_id": "100",
            "order_partner_id": "4291",
            "order_is_to": "0",
            "order_created": "2026-04-05 21:34:38",
            "order_created_by": "7217",
            "order_confirm_user": "0",
            "order_ksc": "0",
            "order_crmode": "create",
            "deleted": "0",
            "order_state_description": "CREATED",
            "order_branch_number": "22",
            "order_partner_number": "2075077",
            "order_partner_name": "ЧА ВЪЗКРЕСЕНИЕ 2",
            "order_partner_street": "СОФИЯ Ж.К.ЛЮЛИН, БЛ.702",
            "DiscountTypeIDFree": "2",
            "DiscountTypeIDNZOK": "1",
            "sendResultErrmsg": "_",
        }
        items = [
            {
                "order_item_id": "",
                "item_id": "1",
                "article_id": "5344",
                "article_number": "237305",
                "CyrName": "БИОКС-КОМПЛЕКС СИРОП 100МЛ",
                "LatName": "",
                "ProducerName": "АЛФА МАРКЕТИНГ",
                "BasePrice": "1.64",
                "SalePrice": "2.16",
                "CustomDiscPct": "0",
                "CustomDiscType": "A",
                "pdDisc": "17.00",
                "pdPrice": "1.85",
                "pdPharmacySellPrice": "2.65",
                "order_id": "0",
                "quantity": "2",
                "quantity_confirmed": "0",
                "RebateInKind": "0",
                "DiscPct": "0",
                "ExpiryDate": "11/2027",
                "MeasureName": "ОП",
                "ProducerCode": "992",
                "MaxPrice": "0.00",
                "NHIFCode": "",
                "NHIFSalePrice": "0.00",
                "NHIFBasePrice": "0.00",
                "NHIFMaxPrice": "0.00",
                "isMedicalPrescription": "0",
                "isWebSaleProhibition": "0",
                "isDrugstoreAllowed": "1",
                "isDrug": "0",
                "isForRefrigerator": "0",
                "AdvertismentText": "",
                "Barcode1": "3800212395164",
                "Barcode2": "",
                "Description": "",
                "lastupdate": "2026-04-05 07:00:02",
                "StockLevel": "0",
                "promo_count": "0",
                "json_promo_list": "[]",
                "deleted": "0",
                "id": "BgShop.model.order.OrderItem-1",
            }
        ]

        payload = phoenix_optimized_module.PhoenixPharmaOptimized._build_commit_payload(phoenix, order_row, items).decode("utf-8")

        self.assertIn("<order_item_count>1</order_item_count>", payload)
        self.assertIn("<TotalQuantity>2</TotalQuantity>", payload)
        self.assertIn("<TotalBasePrice>3.28</TotalBasePrice>", payload)
        self.assertIn("<TotalSalePrice>4.32</TotalSalePrice>", payload)
        self.assertIn("article_id&gt;5344&lt;", payload)

    def test_add_product_to_cart_reloads_order_when_commit_response_drops_existing_items(self):
        phoenix = phoenix_optimized_module.PhoenixPharmaOptimized.__new__(phoenix_optimized_module.PhoenixPharmaOptimized)
        phoenix.remember_action = lambda *_args, **_kwargs: None
        phoenix._current_order_row = {"order_id": "15580946"}
        phoenix._order_item_rows = [
            {"article_id": "existing-1", "CyrName": "EXISTING", "quantity": "3"},
        ]
        phoenix._article_rows_by_name = {
            "TARGET": {
                "article_id": "5344",
                "article_number": "237305",
                "CyrName": "TARGET",
                "LatName": "",
                "ProducerName": "ALFA",
                "BasePrice": "1.64",
                "SalePrice": "2.16",
                "CustomDiscPct": "0",
                "CustomDiscType": "A",
                "pdDisc": "17.00",
                "pdPrice": "1.85",
                "pdPharmacySellPrice": "2.65",
                "ExpiryDate": "11/2027",
                "MeasureName": "OP",
                "ProducerCode": "992",
                "MaxPrice": "0.00",
                "NHIFSalePrice": "0.00",
                "NHIFBasePrice": "0.00",
                "NHIFMaxPrice": "0.00",
                "isMedicalPrescription": "0",
                "isWebSaleProhibition": "0",
                "isDrugstoreAllowed": "1",
                "isDrug": "0",
                "isForRefrigerator": "0",
                "StockLevel": "0",
                "json_promo_list": "[]",
            }
        }
        phoenix._ensure_order_initialized = lambda: phoenix._current_order_row

        def fake_commit(_items):
            phoenix._order_item_rows = [
                {"article_id": "5344", "CyrName": "TARGET", "quantity": "2"},
            ]

        phoenix._commit_order_items = fake_commit
        phoenix.refresh_page = lambda: None
        phoenix._search_for_product = lambda _product_name: object()
        reload_mock = mock.Mock(
            side_effect=lambda: (
                setattr(
                    phoenix,
                    "_order_item_rows",
                    [
                        {"article_id": "existing-1", "CyrName": "EXISTING", "quantity": "3"},
                        {"article_id": "5344", "CyrName": "TARGET", "quantity": "2"},
                    ],
                ),
                phoenix._current_order_row,
            )[1]
        )
        phoenix._reload_order_state = reload_mock

        result = phoenix_optimized_module.PhoenixPharmaOptimized.add_product_to_cart(phoenix, "TARGET", 2)

        self.assertTrue(result)
        reload_mock.assert_called_once()

    def test_add_product_to_cart_falls_back_to_ui_when_api_attempt_leaves_order_unchanged(self):
        phoenix = phoenix_optimized_module.PhoenixPharmaOptimized.__new__(phoenix_optimized_module.PhoenixPharmaOptimized)
        phoenix.remember_action = lambda *_args, **_kwargs: None
        phoenix._current_order_row = {"order_id": "15580946"}
        phoenix._order_item_rows = [
            {"article_id": "existing-1", "CyrName": "EXISTING", "quantity": "1"},
        ]
        phoenix._article_rows_by_name = {
            "TARGET": {
                "article_id": "5344",
                "article_number": "237305",
                "CyrName": "TARGET",
                "LatName": "",
                "ProducerName": "ALFA",
                "BasePrice": "1.64",
                "SalePrice": "2.16",
                "CustomDiscPct": "0",
                "CustomDiscType": "A",
                "pdDisc": "17.00",
                "pdPrice": "1.85",
                "pdPharmacySellPrice": "2.65",
                "ExpiryDate": "11/2027",
                "MeasureName": "OP",
                "ProducerCode": "992",
                "MaxPrice": "0.00",
                "NHIFSalePrice": "0.00",
                "NHIFBasePrice": "0.00",
                "NHIFMaxPrice": "0.00",
                "isMedicalPrescription": "0",
                "isWebSaleProhibition": "0",
                "isDrugstoreAllowed": "1",
                "isDrug": "0",
                "isForRefrigerator": "0",
                "StockLevel": "0",
                "json_promo_list": "[]",
            }
        }
        phoenix._ensure_order_initialized = lambda: phoenix._current_order_row
        phoenix._commit_order_items = lambda _items: None
        phoenix.refresh_page = mock.Mock()
        phoenix._search_for_product = mock.Mock(return_value=object())

        reload_states = [
            [{"article_id": "existing-1", "CyrName": "EXISTING", "quantity": "1"}],
            [
                {"article_id": "existing-1", "CyrName": "EXISTING", "quantity": "1"},
                {"article_id": "5344", "CyrName": "TARGET", "quantity": "2"},
            ],
        ]

        def fake_reload():
            phoenix._order_item_rows = reload_states.pop(0)
            return phoenix._current_order_row

        phoenix._reload_order_state = mock.Mock(side_effect=fake_reload)

        with mock.patch.object(phoenix_optimized_module.PhoenixPharma, "add_product_to_cart", autospec=True, return_value=True) as ui_add_mock:
            result = phoenix_optimized_module.PhoenixPharmaOptimized.add_product_to_cart(phoenix, "TARGET", 2)

        self.assertTrue(result)
        phoenix.refresh_page.assert_called_once()
        phoenix._search_for_product.assert_called_once_with("TARGET")
        self.assertEqual(phoenix._reload_order_state.call_count, 2)
        ui_add_mock.assert_called_once_with(phoenix, 2)

    def test_add_product_to_cart_raises_when_api_attempt_changes_order_ambiguously(self):
        phoenix = phoenix_optimized_module.PhoenixPharmaOptimized.__new__(phoenix_optimized_module.PhoenixPharmaOptimized)
        phoenix.remember_action = lambda *_args, **_kwargs: None
        phoenix._current_order_row = {"order_id": "15580946"}
        phoenix._order_item_rows = [
            {"article_id": "existing-1", "CyrName": "EXISTING", "quantity": "3"},
        ]
        phoenix._article_rows_by_name = {
            "TARGET": {
                "article_id": "5344",
                "article_number": "237305",
                "CyrName": "TARGET",
                "LatName": "",
                "ProducerName": "ALFA",
                "BasePrice": "1.64",
                "SalePrice": "2.16",
                "CustomDiscPct": "0",
                "CustomDiscType": "A",
                "pdDisc": "17.00",
                "pdPrice": "1.85",
                "pdPharmacySellPrice": "2.65",
                "ExpiryDate": "11/2027",
                "MeasureName": "OP",
                "ProducerCode": "992",
                "MaxPrice": "0.00",
                "NHIFSalePrice": "0.00",
                "NHIFBasePrice": "0.00",
                "NHIFMaxPrice": "0.00",
                "isMedicalPrescription": "0",
                "isWebSaleProhibition": "0",
                "isDrugstoreAllowed": "1",
                "isDrug": "0",
                "isForRefrigerator": "0",
                "StockLevel": "0",
                "json_promo_list": "[]",
            }
        }
        phoenix._ensure_order_initialized = lambda: phoenix._current_order_row
        phoenix._commit_order_items = lambda _items: None
        phoenix.refresh_page = mock.Mock()
        phoenix._search_for_product = mock.Mock(return_value=object())
        phoenix._reload_order_state = mock.Mock(
            side_effect=lambda: (
                setattr(
                    phoenix,
                    "_order_item_rows",
                    [
                        {"article_id": "existing-1", "CyrName": "EXISTING", "quantity": "1"},
                        {"article_id": "5344", "CyrName": "TARGET", "quantity": "1"},
                    ],
                ),
                phoenix._current_order_row,
            )[1]
        )

        with self.assertRaisesRegex(RuntimeError, "changed the order unexpectedly"):
            phoenix_optimized_module.PhoenixPharmaOptimized.add_product_to_cart(phoenix, "TARGET", 2)

        phoenix.refresh_page.assert_not_called()


if __name__ == "__main__":
    unittest.main()
