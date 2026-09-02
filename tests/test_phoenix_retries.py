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


ensure_module("pharmacy_distributors")
ensure_module("pharmacy_distributors.common")
models_module = ensure_module("pharmacy_distributors.common.models")
models_module.ScrapedProductInfo = type("ScrapedProductInfo", (), {})

browser_common_module = ensure_module("pharmacy_distributors.common.browser_common")
browser_common_module.BrowserCommon = type("BrowserCommon", (), {})

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
support_ec_module.presence_of_element_located = lambda locator: locator
exceptions_module = ensure_module("selenium.common.exceptions")
exceptions_module.ElementClickInterceptedException = type("ElementClickInterceptedException", (Exception,), {})
exceptions_module.StaleElementReferenceException = type("StaleElementReferenceException", (Exception,), {})
exceptions_module.TimeoutException = type("TimeoutException", (Exception,), {})
exceptions_module.WebDriverException = type("WebDriverException", (Exception,), {})


MODULE_PATH = Path(__file__).resolve().parents[1] / "scraper" / "scraper" / "pharmacy_distributors" / "phoenix" / "phoenix.py"
SPEC = importlib.util.spec_from_file_location("phoenix_module_for_retries", MODULE_PATH)
phoenix_module = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(phoenix_module)


class PhoenixRetryClassificationTests(unittest.TestCase):
    def test_is_retryable_navigation_error_matches_aborted_navigation(self):
        phoenix = phoenix_module.PhoenixPharma.__new__(phoenix_module.PhoenixPharma)

        self.assertTrue(
            phoenix._is_retryable_navigation_error(
                RuntimeError("timeout from aborted by navigation: Not attached to an active page")
            )
        )

    def test_is_retryable_navigation_error_rejects_other_errors(self):
        phoenix = phoenix_module.PhoenixPharma.__new__(phoenix_module.PhoenixPharma)

        self.assertFalse(
            phoenix._is_retryable_navigation_error(
                RuntimeError("element not interactable")
            )
        )


if __name__ == "__main__":
    unittest.main()
