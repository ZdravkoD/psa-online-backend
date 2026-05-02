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
selenium_common_exceptions.StaleElementReferenceException = type("StaleElementReferenceException", (Exception,), {})
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
webdriver_support_expected.alert_is_present = lambda *args, **kwargs: None
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
        self.sting._postback_form_state["ctl00$grid$RadGridResults_ClientState"] = '{"stale":"yes"}'
        self.sting._postback_form_state["ctl00$grid$QtyResults$0"] = "2"
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
        self.assertNotIn("ctl00$grid$RadGridResults_ClientState", payload)
        self.assertNotIn("ctl00$grid$QtyResults$0", payload)

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

    def test_clear_search_result_only_clears_box(self):
        sting = sting_module.StingPharma.__new__(sting_module.StingPharma)
        sting.lastSearchWasEmpty = False
        sting._last_search_result_name = "OLD"
        sting.SEARCH_BOX_XPATH = "//search"
        sting.remember_action = lambda *_args, **_kwargs: None
        sting.store_temporary_screenshot = lambda *_args, **_kwargs: None
        search_box = mock.Mock()
        sting.browser = mock.Mock()
        sting.browser.find_element.return_value = search_box

        sting_module.StingPharma._clearSearchResult(sting)

        self.assertTrue(sting.lastSearchWasEmpty)
        self.assertIsNone(sting._last_search_result_name)
        search_box.clear.assert_called_once_with()
        search_box.send_keys.assert_not_called()

    def test_search_for_product_uses_result_wait_instead_of_spinner_cycle(self):
        sting = sting_module.StingPharma.__new__(sting_module.StingPharma)
        sting.SEARCH_BOX_XPATH = "//search"
        sting.SEARCH_BUTTON_XPATH = "//button"
        sting.lastSearchWasEmpty = True
        sting.remember_action = lambda *_args, **_kwargs: None
        sting.store_temporary_screenshot = lambda *_args, **_kwargs: None
        sting._clearSearchResult = mock.Mock()
        sting._wait_for_interactable_xpath = mock.Mock()

        search_box = mock.Mock()
        search_button = mock.Mock()
        add_input = mock.Mock()
        add_input.tag_name = "input"
        add_input.is_displayed.return_value = True
        add_input.is_enabled.return_value = True

        sting.browser = mock.Mock()
        sting.browser.find_element.side_effect = [search_box, search_box, search_button]
        sting.browser.find_elements.return_value = [add_input]
        sting._wait_for_interactable_xpath.return_value = add_input

        element, alternative_names = sting_module.StingPharma._search_for_product(sting, "TARGET")

        self.assertIs(element, add_input)
        self.assertIsNone(alternative_names)
        sting._clearSearchResult.assert_called_once_with()
        sting._wait_for_interactable_xpath.assert_called_once()
        self.assertEqual(sting._last_search_result_name, "TARGET")
        self.assertFalse(sting.lastSearchWasEmpty)

    def test_capture_postback_form_state_ignores_grid_inputs(self):
        sting = sting_module.StingPharma.__new__(sting_module.StingPharma)
        sting._get_name_filter_box_field_name = lambda: "NameFilterBox"
        sting._get_name_filter_box_client_state_field_name = lambda: "NameFilterBoxClientState"

        hidden_viewstate = mock.Mock()
        hidden_viewstate.get_attribute.side_effect = lambda name: {
            "name": "__VIEWSTATE",
            "type": "hidden",
            "value": "viewstate",
        }.get(name)
        search_box = mock.Mock()
        search_box.get_attribute.side_effect = lambda name: {
            "name": "NameFilterBox",
            "type": "text",
            "value": "needle",
        }.get(name)
        qty_input = mock.Mock()
        qty_input.get_attribute.side_effect = lambda name: {
            "name": "ctl00$grid$QtyResults$0",
            "type": "text",
            "value": "2",
        }.get(name)
        grid_state = mock.Mock()
        grid_state.get_attribute.side_effect = lambda name: {
            "name": "ctl00$grid$RadGridResults_ClientState",
            "type": "hidden",
            "value": '{"stale":"yes"}',
        }.get(name)

        sting.browser = mock.Mock()
        sting.browser.find_elements.return_value = [hidden_viewstate, search_box, qty_input, grid_state]

        state = sting_module.StingPharma._capture_postback_form_state_from_browser(sting)

        self.assertEqual(state, {"__VIEWSTATE": "viewstate", "NameFilterBox": "needle"})

    def test_submit_add_to_cart_retries_on_stale_click(self):
        sting = sting_module.StingPharma.__new__(sting_module.StingPharma)
        sting.store_temporary_screenshot = lambda *_args, **_kwargs: None

        quantity_input = mock.Mock()
        add_button_first = mock.Mock()
        add_button_second = mock.Mock()
        add_button_first.click.side_effect = sting_module.StaleElementReferenceException("stale")
        sting._wait_for_interactable_xpath = mock.Mock(
            side_effect=[quantity_input, add_button_first, quantity_input, add_button_second]
        )

        with mock.patch.object(sting_module.time, "sleep") as sleep_mock:
            sting_module.StingPharma._submit_add_to_cart(sting, 2)

        self.assertEqual(quantity_input.clear.call_count, 2)
        self.assertEqual(quantity_input.send_keys.call_count, 2)
        quantity_input.send_keys.assert_called_with("2")
        add_button_first.click.assert_called_once_with()
        add_button_second.click.assert_called_once_with()
        sleep_mock.assert_called_once_with(sting_module.StingPharma.ADD_TO_CART_RETRY_DELAY_SECONDS)

    def test_add_product_to_cart_uses_fast_restore_without_refresh(self):
        sting = sting_module.StingPharma.__new__(sting_module.StingPharma)
        sting._last_search_result_name = "TARGET"
        sting.remember_action = lambda *_args, **_kwargs: None
        sting._submit_add_to_cart = mock.Mock()
        sting._restore_search_state_after_add = mock.Mock()
        sting.refresh_page = mock.Mock()
        sting._postback_form_state = {"state": "old"}

        result = sting_module.StingPharma.add_product_to_cart(sting, "TARGET", 3)

        self.assertTrue(result)
        sting._submit_add_to_cart.assert_called_once_with(3)
        sting._restore_search_state_after_add.assert_called_once_with()
        sting.refresh_page.assert_not_called()
        self.assertEqual(sting._postback_form_state, {"state": "old"})
        self.assertIsNone(sting._last_search_result_name)

    def test_add_product_to_cart_refreshes_when_fast_restore_fails(self):
        sting = sting_module.StingPharma.__new__(sting_module.StingPharma)
        sting._last_search_result_name = "TARGET"
        sting.remember_action = lambda *_args, **_kwargs: None
        sting._submit_add_to_cart = mock.Mock()
        sting._restore_search_state_after_add = mock.Mock(side_effect=RuntimeError("boom"))
        sting.refresh_page = mock.Mock()
        sting._postback_form_state = {"state": "old"}

        result = sting_module.StingPharma.add_product_to_cart(sting, "TARGET", 1)

        self.assertTrue(result)
        sting.refresh_page.assert_called_once_with()
        self.assertIsNone(sting._postback_form_state)
        self.assertIsNone(sting._last_search_result_name)

    def test_restore_search_state_after_add_invalidates_postback_cache(self):
        sting = sting_module.StingPharma.__new__(sting_module.StingPharma)
        sting.SEARCH_BOX_XPATH = "//search"
        sting._postback_form_state = {"stale": "yes"}
        sting.browser = mock.Mock()
        sting.browser.find_elements.return_value = []

        wait_instance = mock.Mock()
        wait_instance.until.return_value = mock.Mock()

        with mock.patch.object(sting_module, "WebDriverWait", return_value=wait_instance):
            sting_module.StingPharma._restore_search_state_after_add(sting)

        self.assertIsNone(sting._postback_form_state)


if __name__ == "__main__":
    unittest.main()
