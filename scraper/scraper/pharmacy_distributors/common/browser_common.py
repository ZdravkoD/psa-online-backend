import os
from datetime import datetime
from typing import List, Tuple, Deque
import logging
from collections import deque

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

    def get_product_name_and_price(self, product_id) -> Tuple[str, float]:
        raise NotImplementedError("Subclasses must implement this method")

    def add_product_to_cart(self, product_id: str, quantity: int):
        raise NotImplementedError("Subclasses must implement this method")

    def get_name(self) -> str:
        return self.name

    def get_priority(self) -> int:
        return self.priority
