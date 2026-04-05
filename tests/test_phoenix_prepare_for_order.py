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

browser_common_module = ensure_module("pharmacy_distributors.common.browser_common")


class StubBrowserCommon:
    def remember_action(self, action: str):
        self.last_action = action

    def store_temporary_screenshot(self):
        return None


browser_common_module.BrowserCommon = StubBrowserCommon

configuration_module = ensure_module("configuration")
configuration_common_module = ensure_module("configuration.common")
configuration_common_module.DistributorConfig = type("DistributorConfig", (), {})

ensure_module("selenium")
ensure_module("selenium.webdriver")
keys_module = ensure_module("selenium.webdriver.common.keys")
keys_module.Keys = type("Keys", (), {"RETURN": "RETURN"})
by_module = ensure_module("selenium.webdriver.common.by")
by_module.By = type("By", (), {"XPATH": "xpath", "CSS_SELECTOR": "css"})
ensure_module("selenium.webdriver.support")
support_ui_module = ensure_module("selenium.webdriver.support.ui")
support_ui_module.WebDriverWait = type("WebDriverWait", (), {})
support_ec_module = ensure_module("selenium.webdriver.support.expected_conditions")
support_ec_module.element_to_be_clickable = lambda locator: locator
selenium_exceptions_module = ensure_module("selenium.common.exceptions")
selenium_exceptions_module.ElementClickInterceptedException = type("ElementClickInterceptedException", (Exception,), {})
selenium_exceptions_module.TimeoutException = type("TimeoutException", (Exception,), {})
selenium_exceptions_module.WebDriverException = type("WebDriverException", (Exception,), {})


MODULE_PATH = Path(__file__).resolve().parents[1] / "scraper" / "scraper" / "pharmacy_distributors" / "phoenix" / "phoenix.py"
SPEC = importlib.util.spec_from_file_location("phoenix_module", MODULE_PATH)
phoenix_module = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(phoenix_module)


class PhoenixPrepareForOrderTests(unittest.TestCase):
    def test_prepare_for_order_fails_immediately_when_client_selection_fails(self):
        phoenix = phoenix_module.PhoenixPharma.__new__(phoenix_module.PhoenixPharma)
        phoenix.pharmacyID = "tolstoy"
        phoenix.browser = mock.Mock()
        phoenix.store_temporary_screenshot = mock.Mock()
        phoenix.remember_action = mock.Mock()

        clickable_element = mock.Mock()
        phoenix.browser.find_element.return_value = clickable_element

        wait_mask = mock.Mock()
        wait_mask.until_not.return_value = True
        wait_click_success = mock.Mock()
        wait_click_success.until.return_value = clickable_element
        wait_click_failure = mock.Mock()
        wait_click_failure.until.side_effect = RuntimeError("not found")

        with mock.patch.object(
            phoenix_module,
            "WebDriverWait",
            side_effect=[wait_mask, wait_click_success, wait_mask, wait_mask, wait_click_success, wait_click_failure],
        ):
            with self.assertRaisesRegex(ValueError, "Phoenix client with pharmacy ID 'tolstoy' was not found or could not be selected."):
                phoenix.prepare_for_order()


if __name__ == "__main__":
    unittest.main()
