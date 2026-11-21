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

common_models_module = ensure_module("pharmacy_distributors.common.models")
common_models_module.ScrapedProductInfo = type("ScrapedProductInfo", (), {})

common_utils_module = ensure_module("pharmacy_distributors.common.utils")
common_utils_module.check_webdriver_is_present = lambda: None
common_utils_module.get_browser_options = lambda: None

ensure_module("selenium")
webdriver_module = ensure_module("selenium.webdriver")
webdriver_module.Chrome = type("Chrome", (), {})
ensure_module("selenium.webdriver.common")
by_module = ensure_module("selenium.webdriver.common.by")
by_module.By = type("By", (), {})
ensure_module("selenium.webdriver.chrome")
chrome_webdriver_module = ensure_module("selenium.webdriver.chrome.webdriver")
chrome_webdriver_module.WebDriver = type("WebDriver", (), {})
selenium_exceptions_module = ensure_module("selenium.common.exceptions")
selenium_exceptions_module.TimeoutException = type("TimeoutException", (Exception,), {})
selenium_exceptions_module.WebDriverException = type("WebDriverException", (Exception,), {})


MODULE_PATH = Path(__file__).resolve().parents[1] / "scraper" / "scraper" / "pharmacy_distributors" / "common" / "browser_common.py"
SPEC = importlib.util.spec_from_file_location("browser_common_module", MODULE_PATH)
browser_common_module = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(browser_common_module)


class BrowserCommonDebugContextTests(unittest.TestCase):
    def test_format_debug_context_marks_blank_startup_page(self):
        scraper = browser_common_module.BrowserCommon("Phoenix", 20, shouldInitBrowser=False)
        scraper.browser = types.SimpleNamespace(
            title="",
            current_url="data:,",
            window_handles=["tab-1"],
            current_window_handle="tab-1",
            page_source="",
            capabilities={"browserName": "chrome", "browserVersion": "135.0"},
            execute_script=lambda script: "complete",
        )

        result = scraper.format_debug_context()

        self.assertIn("Current URL: data:,", result)
        self.assertIn("Document ready state: complete", result)
        self.assertIn("Page source length: 0", result)
        self.assertIn("Browser: chrome 135.0", result)
        self.assertIn(
            "Browser state: blank startup page; navigation may not have started or browser failed before first page load",
            result,
        )

    def test_open_url_retries_when_browser_stays_on_blank_page(self):
        scraper = browser_common_module.BrowserCommon("Phoenix", 20, shouldInitBrowser=False)

        first_browser = types.SimpleNamespace(
            current_url="data:,",
            get=lambda url: None,
        )
        second_browser = types.SimpleNamespace(
            current_url="https://b2b.phoenixpharma.bg/bg/build/production/BgShop/index.php",
            get=lambda url: None,
        )

        browsers = iter([second_browser])
        restart_calls = []

        scraper.browser = first_browser

        def restart_browser():
            restart_calls.append("restart")
            scraper.browser = next(browsers)

        scraper.restart_browser = restart_browser

        scraper.open_url("https://b2b.phoenixpharma.bg/bg/build/production/BgShop/index.php", retries=2)

        self.assertEqual(restart_calls, ["restart"])


if __name__ == "__main__":
    unittest.main()
