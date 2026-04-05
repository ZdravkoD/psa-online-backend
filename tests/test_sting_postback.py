import importlib.util
import sys
import types
import unittest
from pathlib import Path


def ensure_module(name: str) -> types.ModuleType:
    module = sys.modules.get(name)
    if module is None:
        module = types.ModuleType(name)
        sys.modules[name] = module
    return module


ensure_module("requests").Session = type("Session", (), {})
ensure_module("pharmacy_distributors")
ensure_module("pharmacy_distributors.common")
models_module = ensure_module("pharmacy_distributors.common.models")


class StubScrapedProductInfo:
    def __init__(self, name, price, is_on_promotion, alternative_names):
        self.name = name
        self.price = price
        self.is_on_promotion = is_on_promotion
        self.alternative_names = alternative_names if alternative_names is not None else []


models_module.ScrapedProductInfo = StubScrapedProductInfo

browser_common_module = ensure_module("pharmacy_distributors.common.browser_common")


class StubBrowserCommon:
    def __init__(self, *_args, **_kwargs):
        pass

    def remember_action(self, *_args, **_kwargs):
        pass


browser_common_module.BrowserCommon = StubBrowserCommon

configuration_module = ensure_module("configuration.common")
configuration_module.DistributorConfig = type(
    "DistributorConfig",
    (),
    {
        "Sting": type(
            "StingConfig",
            (),
            {"CONFIG": type("Config", (), {"get_all_users": staticmethod(lambda: [])})()},
        )()
    },
)

ensure_module("selenium")
selenium_common = ensure_module("selenium.common")
selenium_common_exceptions = ensure_module("selenium.common.exceptions")
selenium_common_exceptions.TimeoutException = type("TimeoutException", (Exception,), {})
selenium_common_exceptions.WebDriverException = type("WebDriverException", (Exception,), {})

webdriver_module = ensure_module("selenium.webdriver")
webdriver_common = ensure_module("selenium.webdriver.common")
webdriver_common_by = ensure_module("selenium.webdriver.common.by")
webdriver_common_by.By = type("By", (), {"XPATH": "xpath", "CSS_SELECTOR": "css"})
webdriver_common_keys = ensure_module("selenium.webdriver.common.keys")
webdriver_common_keys.Keys = type("Keys", (), {"RETURN": "\n"})
webdriver_support = ensure_module("selenium.webdriver.support")
webdriver_support_expected = ensure_module("selenium.webdriver.support.expected_conditions")
webdriver_support_expected.element_to_be_clickable = lambda *args, **kwargs: None
webdriver_support_ui = ensure_module("selenium.webdriver.support.ui")
webdriver_support_ui.WebDriverWait = type("WebDriverWait", (), {})
webdriver_remote = ensure_module("selenium.webdriver.remote")
webdriver_remote_webelement = ensure_module("selenium.webdriver.remote.webelement")
webdriver_remote_webelement.WebElement = type("WebElement", (), {})

MODULE_PATH = Path(__file__).resolve().parents[1] / "scraper" / "scraper" / "pharmacy_distributors" / "sting" / "sting.py"
SPEC = importlib.util.spec_from_file_location("sting_module_for_tests", MODULE_PATH)
sting_module = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(sting_module)


class StingPostbackTests(unittest.TestCase):
    def setUp(self):
        self.sting = sting_module.StingPharma.__new__(sting_module.StingPharma)
        self.sting._postback_form_state = {
            "__VIEWSTATE": "viewstate",
            "__EVENTVALIDATION": "eventvalidation",
            "ctl00$ctl00$ctl00$ctl00$ctl00$ContentPlaceHolderBody$ContentPlaceHolderBody$ContentPlaceHolderBody$ContentPlaceHolderBody$ContentPlaceHolderBody$RadComboBoxSearchType": "съдържа",
            "ctl00_ctl00_ctl00_ctl00_ctl00_ContentPlaceHolderBody_ContentPlaceHolderBody_ContentPlaceHolderBody_ContentPlaceHolderBody_ContentPlaceHolderBody_RadComboBoxSearchType_ClientState": '{"value":"1"}',
        }

    def test_build_search_postback_payload_includes_expected_fields(self):
        payload = sting_module.StingPharma._build_search_postback_payload(self.sting, "биокс-комплекс сироп 100мл")

        self.assertEqual(payload["__ASYNCPOST"], "true")
        self.assertEqual(payload["__VIEWSTATE"], "viewstate")
        self.assertIn("SearchButton", payload["ctl00$ctl00$ctl00$ctl00$ctl00$RadScriptManager1"])
        self.assertEqual(
            payload[
                "ctl00$ctl00$ctl00$ctl00$ctl00$ContentPlaceHolderBody$ContentPlaceHolderBody$ContentPlaceHolderBody$ContentPlaceHolderBody$ContentPlaceHolderBody$NameFilterBox"
            ],
            "биокс-комплекс сироп 100мл",
        )
        self.assertIn(
            '"valueAsString":"биокс-комплекс сироп 100мл"',
            payload[
                "ctl00_ctl00_ctl00_ctl00_ctl00_ContentPlaceHolderBody_ContentPlaceHolderBody_ContentPlaceHolderBody_ContentPlaceHolderBody_ContentPlaceHolderBody_NameFilterBox_ClientState"
            ],
        )

    def test_parse_search_results_panel_html_returns_empty_for_no_records(self):
        response = (
            "1|#||4|100|updatePanel|someRadGridResultsPanel|"
            "<div><table><tbody><tr class=\"rgNoRecords\"><td>Няма открити артикули.</td></tr></tbody></table></div>"
            "|0|hiddenField|__VIEWSTATE|next|"
        )

        rows = sting_module.StingPharma._parse_search_results_panel_html(self.sting, response)

        self.assertEqual(rows, [])

    def test_parse_search_results_panel_html_returns_single_row(self):
        response = """
1|#||4|4099|updatePanel|ctl00_any_RadGridResultsPanel|<div id="grid">
<table class="rgMasterTable"><thead><tr>
<th style="display:none;">ProductID</th>
<th>Артикул</th>
<th>Код НЗОК</th>
<th>Производител</th>
<th>Срок на годност</th>
<th>Преп. цена €</th>
<th>Преп. цена Лв.</th>
<th>Цена €</th>
<th>%ТО</th>
<th>Цена с ТО €</th>
<th>Добавяне</th>
</tr></thead><tbody>
<tr class="rgRow">
<td style="display:none;">23223</td>
<td>БИОКС-КОМПЛЕКС сироп 100мл.&nbsp;</td>
<td>&nbsp;</td>
<td>АЛФА МАРКЕТИНГ ЕООД&nbsp;</td>
<td align="center">31.12.2027&nbsp;</td>
<td align="right">2.65</td>
<td align="right">5.19</td>
<td align="right">2.16</td>
<td align="right">14.00</td>
<td align="right">1.88</td>
<td align="center"><input id="QtyResults" /><input title="Добави количеството към количката" /></td>
</tr>
</tbody></table>
<input name="ctl00_grid_RadGridResults_ClientState" value="" />
</div>|0|hiddenField|__VIEWSTATE|next-viewstate|
"""

        rows = sting_module.StingPharma._parse_search_results_panel_html(self.sting, response)

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["name"], "БИОКС-КОМПЛЕКС сироп 100мл.")
        self.assertEqual(rows[0]["price"], 1.88)
        self.assertTrue(rows[0]["has_add_input"])


if __name__ == "__main__":
    unittest.main()
