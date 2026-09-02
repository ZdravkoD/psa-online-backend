import logging
import os
from threading import Lock
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import WebDriverException

# Create a logger for this module
logger = logging.getLogger(__name__)
_webdriver_check_lock = Lock()
_webdriver_was_checked = False


def check_webdriver_is_present():
    global _webdriver_was_checked
    if _webdriver_was_checked:
        return

    with _webdriver_check_lock:
        if _webdriver_was_checked:
            return

        driver = None
        try:
            # Specify the path if it's not added to PATH
            # driver = webdriver.Chrome(executable_path="/path/to/chromedriver")
            driver = webdriver.Chrome(get_browser_options())
            driver.get("http://www.google.com")
            logger.info("ChromeDriver is available and functional.")
            _webdriver_was_checked = True
        except WebDriverException as e:
            logger.exception(f"Error with ChromeDriver: {e}")
            raise e
        finally:
            if driver is not None:
                try:
                    driver.quit()
                except Exception:
                    logger.warning("Failed to quit ChromeDriver probe session cleanly.")


def get_browser_options() -> Options:
    options = Options()
    options.add_argument("--headless")  # Ensure GUI is off
    options.add_argument("--no-sandbox")  # Bypass OS security model
    options.add_argument("--disable-dev-shm-usage")  # Overcome limited resource problems
    options.add_argument("--disable-gpu")  # Applicable to Windows environments
    options.add_argument("--disable-software-rasterizer")

    if str(os.getenv("CHROME_ENABLE_PERFORMANCE_LOGS", "")).lower() in {"1", "true", "yes"}:
        options.set_capability("goog:loggingPrefs", {"performance": "ALL"})

    return options
