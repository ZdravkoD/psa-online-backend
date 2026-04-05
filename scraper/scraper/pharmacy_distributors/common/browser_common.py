import os
from datetime import datetime
from typing import List, Tuple, Deque
import logging
from collections import deque

from pharmacy_distributors.common.models import ScrapedProductInfo
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.webdriver import WebDriver

from pharmacy_distributors.common.utils import check_webdriver_is_present, get_browser_options

# Create a logger for this module
logger = logging.getLogger(__name__)


class BrowserCommon():
    def __init__(self, name: str, priority: int, shouldInitBrowser=True):
        self.browser: WebDriver = None
        if shouldInitBrowser:
            self.initBrowser()
        self.name = name
        self.priority = priority
        self.temporary_screenshotts: Deque[bytes] = deque(maxlen=3)
        self.recent_actions: Deque[str] = deque(maxlen=8)
        self.current_action = "browser initialized"

    def initBrowser(self):
        # Raises WebDriverException if the driver is not available
        check_webdriver_is_present()

        self.browser = webdriver.Chrome(get_browser_options())

    def hasInternetConnection(self):
        try:
            self.browser.find_element(By.XPATH, "//span[@jsselect='heading' and @jsvalues='.innerHTML:msg']")
            return False
        except Exception:
            return True

    def saveScreenshot(self):
        logger.info("BrowserCommon: Saving Screenshot...")
        dt_string = datetime.now().strftime("%Y.%m.%d_%H.%M.%S")
        cwd = os.getcwd()
        screenShotName = cwd + "/Screenshots/" + dt_string + "_" + self.__class__.__name__ + "_ScreenshotOnException.png"
        logger.info("BrowserCommon: Storing Screenshot: %s", screenShotName)
        self.browser.save_screenshot(screenShotName)

    def getScreenshot(self) -> Tuple[bytes, str]:
        logger.info("BrowserCommon: Getting Screenshot...")
        dt_string = datetime.now().strftime("%Y.%m.%d_%H.%M.%S")
        screenShotName = dt_string + "_" + self.__class__.__name__ + "_ScreenshotOnException.png"
        logger.info("BrowserCommon: Returning Screenshot: %s", screenShotName)
        return self.browser.get_screenshot_as_png(), screenShotName

    def store_temporary_screenshot(self):
        """
        Stores the 3 most recent screenshots in the temporary_screenshotts deque
        """
        screenshot = self.browser.get_screenshot_as_png()
        self.temporary_screenshotts.appendleft(screenshot)

    def remember_action(self, action: str):
        self.current_action = action
        self.recent_actions.appendleft(action)
        logger.info("%s: %s", self.__class__.__name__, action)

    def _safe_get_current_url(self) -> str:
        try:
            return self.browser.current_url
        except Exception as exc:
            return f"<unavailable: {exc}>"

    def _safe_get_title(self) -> str:
        try:
            return self.browser.title
        except Exception as exc:
            return f"<unavailable: {exc}>"

    def _safe_get_window_handles(self) -> str:
        try:
            return str(len(self.browser.window_handles))
        except Exception as exc:
            return f"<unavailable: {exc}>"

    def get_debug_context(self) -> dict:
        return {
            "scraper": self.get_name(),
            "current_action": self.current_action,
            "recent_actions": list(self.recent_actions),
            "page_title": self._safe_get_title(),
            "current_url": self._safe_get_current_url(),
            "window_handles": self._safe_get_window_handles(),
        }

    def format_debug_context(self) -> str:
        context = self.get_debug_context()
        lines = [
            f"Scraper: {context['scraper']}",
            f"Current action: {context['current_action']}",
            f"Page title: {context['page_title']}",
            f"Current URL: {context['current_url']}",
            f"Window handles: {context['window_handles']}",
        ]
        if context["recent_actions"]:
            lines.append("Recent actions:")
            lines.extend(f"- {action}" for action in context["recent_actions"])
        return "\n".join(lines)

    def get_temporary_screenshots(self) -> List[Tuple[bytes, str]]:
        screenshots_with_names = []
        for screenshot in self.temporary_screenshotts:
            dt_string = datetime.now().strftime("%Y.%m.%d_%H.%M.%S")
            screenShotName = dt_string + "_" + self.__class__.__name__ + "_TemporaryScreenshot.png"
            screenshots_with_names.append((screenshot, screenShotName))
        return screenshots_with_names

    def setBrowserToDefaultPosition(self):
        self.browser.set_window_position(0, 0)

    def finish(self):
        self.browser.quit()

    def login(self):
        raise NotImplementedError("Subclasses must implement this method")

    def prepare_for_order(self):
        raise NotImplementedError("Subclasses must implement this method")

    def refresh_page(self):
        raise NotImplementedError("Subclasses must implement this method")

    def get_product_name_and_price(self, product_id) -> ScrapedProductInfo:
        raise NotImplementedError("Subclasses must implement this method")

    def add_product_to_cart(self, product_id: str, quantity: int):
        raise NotImplementedError("Subclasses must implement this method")

    def get_name(self) -> str:
        return self.name

    def get_priority(self) -> int:
        return self.priority
