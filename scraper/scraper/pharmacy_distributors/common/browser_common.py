import os
from datetime import datetime

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By

from pharmacy_distributors.common.utils import check_webdriver_is_present


class BrowserCommon():
    def __init__(self, name: str, priority: int, shouldInitBrowser=True):
        if shouldInitBrowser:
            self.initBrowser()
        self.name = name
        self.priority = priority

    def initBrowser(self):
        # Raises WebDriverException if the driver is not available
        check_webdriver_is_present()

        options = Options()
        # options.add_argument('--headless')  # Run headless Chromium
        # options.add_argument('--no-sandbox')  # Bypass OS security model
        # options.add_argument('--disable-dev-shm-usage')  # Overcome limited resource problems
        options.add_experimental_option('excludeSwitches', ['enable-logging'])
        self.browser = webdriver.Chrome(options)

    def hasInternetConnection(self):
        try:
            self.browser.find_element(By.XPATH, "//span[@jsselect='heading' and @jsvalues='.innerHTML:msg']")
            return False
        except Exception:
            return True

    def saveScreenshot(self):
        print("BrowserCommon: Saving Screenshot...")
        dt_string = datetime.now().strftime("%Y.%m.%d_%H.%M.%S")
        cwd = os.getcwd()
        screenShotName = cwd + "/Screenshots/" + dt_string + "_" + self.__class__.__name__ + "_ScreenshotOnException.png"
        print("BrowserCommon: Storing Screenshot: %s", screenShotName)
        self.browser.save_screenshot(screenShotName)

    def getScreenshot(self) -> tuple[bytes, str]:
        print("BrowserCommon: Getting Screenshot...")
        dt_string = datetime.now().strftime("%Y.%m.%d_%H.%M.%S")
        screenShotName = dt_string + "_" + self.__class__.__name__ + "_ScreenshotOnException.png"
        print("BrowserCommon: Returning Screenshot: %s", screenShotName)
        return self.browser.get_screenshot_as_png(), screenShotName

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

    def get_product_name_and_price(self, product_id) -> tuple[str, float]:
        raise NotImplementedError("Subclasses must implement this method")

    def add_product_to_cart(self, product_id: str, quantity: int):
        raise NotImplementedError("Subclasses must implement this method")

    def get_name(self) -> str:
        return self.name

    def get_priority(self) -> int:
        return self.priority
