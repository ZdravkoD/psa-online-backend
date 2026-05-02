import logging
import math
from typing import Tuple

from pharmacy_distributors.common.models import ScrapedProductInfo
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import ElementClickInterceptedException, StaleElementReferenceException, TimeoutException, WebDriverException

from pharmacy_distributors.common.browser_common import BrowserCommon
from configuration.common import DistributorConfig


SELECTOR_SPELLCHECK = "//div[contains(@data-componentid, 'order-spellcheckwindow')]//div[contains(@class, 'x-tool-tool-el')]"
SELECTOR_VISIBLE_MASK = "//div[contains(@class, 'x-mask') and not(contains(@style, 'display: none'))]"
# Create a logger for this module
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
# -*- coding: utf-8 -*-


class PhoenixPharma(BrowserCommon):

    def __init__(self, pharmacyID: str, shouldInitBrowser=True):
        logger.info("PhoenixPharma.__init__()")

        super().__init__("Phoenix", 20, shouldInitBrowser)

        self.pharmacyID = pharmacyID

        self.LOGIN_PAGE = 'https://b2b.phoenixpharma.bg/bg/build/production/BgShop/index.php'
        # dummy page is used before login in order to navigate to the domain and set the `cookiesAsked` cookie
        self.DUMMY_PAGE = 'https://b2b.phoenixpharma.bg/dummy_page'
        all_users = DistributorConfig.Phoenix.CONFIG.get_all_users()
        for credential in all_users:
            if pharmacyID == credential.id:
                self.username = credential.username
                self.password = credential.password
                break
        else:
            raise ValueError("Pharmacy ID not found in Phoenix config")

        # self.username = 'pc541dibo'
        # self.password = 'pc541dibo'

        self.SEARCH_BOX_XPATH = "//fieldset[starts-with(@aria-label, 'Търсене в номенклатура')]//input[starts-with(@id,'textfield')" \
                                + " and "\
                                + "starts-with(@name, 'textfield')]"
        self.SEARCH_BUTTON_CSS_SELECTOR = "span.fa-search"
        self.PRODUCT_PLUS_BUTTON_XPATH = "//span[text()='Добави']/ancestor::*/div[contains(@role,'grid')]//span[text()='+']"
        self.ROW_WITH_EXPIRY_DATE_XPATH = "//div[contains(@class, 'x-grid-cell-inner') and text() = 'Срок на годност']"

        self.lastSearchWasEmpty = True

    def _is_retryable_navigation_error(self, exc: Exception) -> bool:
        lowered = str(exc).lower()
        return "aborted by navigation" in lowered or "not attached to an active page" in lowered

    def _wait_until_mask_is_gone(self, timeout: float = 10):
        try:
            WebDriverWait(self.browser, timeout).until_not(
                EC.presence_of_element_located((By.XPATH, SELECTOR_VISIBLE_MASK))
            )
        except TimeoutException:
            logger.info("PhoenixPharma: loading mask did not disappear within %s seconds", timeout)

    def _wait_for_interactable_xpath(self, xpath: str, timeout: float, poll_frequency: float = 0.1):
        def find_interactable(_browser):
            try:
                elements = _browser.find_elements(By.XPATH, xpath)
            except StaleElementReferenceException:
                return False

            for element in elements:
                try:
                    if element.is_displayed() and element.is_enabled():
                        return element
                except StaleElementReferenceException:
                    continue
            return False

        return WebDriverWait(self.browser, timeout, poll_frequency=poll_frequency).until(find_interactable)

    def _search_for_product_once(self, product_name: str):
        self._clearSearchResult()
        logger.info("PhoenixPharma:_search_for_product(): product_name:" + product_name)
        self.remember_action(f"Searching Phoenix UI for product '{product_name}'")
        search_box = WebDriverWait(self.browser, 10).until(EC.element_to_be_clickable((By.XPATH, self.SEARCH_BOX_XPATH)))
        search_box.clear()
        search_box.send_keys(product_name)
        self.store_temporary_screenshot()
        search_button = WebDriverWait(self.browser, 10).until(EC.element_to_be_clickable((By.CSS_SELECTOR, self.SEARCH_BUTTON_CSS_SELECTOR)))
        search_button.click()

        # if spellcheck popup appears, hide it
        try:
            element = self._wait_for_interactable_xpath(
                SELECTOR_SPELLCHECK + "|" + self.PRODUCT_PLUS_BUTTON_XPATH,
                timeout=2,
            )
            if element.tag_name == 'div':
                logger.info("PhoenixPharma: Closing spellcheck")
                # spellcheck is triggered only if there are no results, so return None
                element.click()
                return None
        except Exception:
            # Neither spellcheck nor result was found, so return None
            return None

        number_of_results = len(self.browser.find_elements(By.XPATH, self.PRODUCT_PLUS_BUTTON_XPATH))
        self.lastSearchWasEmpty = number_of_results == 0
        return element

    def login(self):
        last_error = None
        for attempt in range(1, 4):
            try:
                self.remember_action("Opening Phoenix login page")
                self.open_url(self.DUMMY_PAGE, retries=1)
                self.browser.add_cookie({'name': 'cookiesAsked', 'value': 'true'})
                self.browser.add_cookie({'name': 'cookiesAllowedMarketing', 'value': 'false'})
                self.browser.add_cookie({'name': 'cookiesAllowedAnalytical', 'value': 'false'})
                self.open_url(self.LOGIN_PAGE, retries=1)
                break
            except Exception as exc:
                last_error = exc
                logger.warning("PhoenixPharma: Login page bootstrap attempt %s/3 failed: %s", attempt, exc)
                if attempt == 3:
                    raise
                self.restart_browser()
        else:
            raise last_error

        self.store_temporary_screenshot()
        self.remember_action(f"Entering Phoenix username for pharmacy {self.username}")
        self.browser.find_element(By.CSS_SELECTOR, "input[name='loginUsername']").send_keys(self.username)
        self.browser.find_element(By.CSS_SELECTOR, "input[name='loginPasswordText']").click()
        self.browser.find_element(By.CSS_SELECTOR, "input[name='loginPasswordText']").send_keys(self.password)
        self.store_temporary_screenshot()
        self.remember_action("Submitting Phoenix login form")
        self.browser.find_element(By.CSS_SELECTOR, "input[name='loginPasswordText']").send_keys(Keys.RETURN)

    def prepare_for_order(self):
        self.remember_action("Opening Phoenix order menu")
        self._wait_until_mask_is_gone()
        WebDriverWait(self.browser, 2).until(EC.element_to_be_clickable((By.XPATH, "//span[contains(text(), 'Поръчка')]"))).click()
        self.store_temporary_screenshot()
        self.remember_action("Starting Phoenix free order")
        self._wait_until_mask_is_gone()
        self.browser.find_element(By.XPATH, "//span[contains(text(), 'Нова поръчка свободна')]").click()
        self._wait_until_mask_is_gone()

        self.remember_action(f"Selecting Phoenix client with pharmacy ID {self.pharmacyID}")
        partner_input = WebDriverWait(self.browser, 10).until(EC.element_to_be_clickable((By.CSS_SELECTOR, "input[name='order_partner_id']")))
        partner_input.clear()
        partner_input.send_keys(self.pharmacyID)
        try:
            element = WebDriverWait(self.browser, 5)\
                .until(EC.element_to_be_clickable((By.XPATH, "//div[contains(@class, 'x-grid-cell-inner') and text() = '" + self.pharmacyID + "']")))
            element.click()
            self._wait_until_mask_is_gone()
        except Exception as exc:
            logger.error("PhoenixPharma:prepare_for_order(): Couldn't find the pharmacy with ID %s", self.pharmacyID)
            raise ValueError(
                f"Phoenix client with pharmacy ID '{self.pharmacyID}' was not found or could not be selected."
            ) from exc

    def _hide_spellcheck(self):
        self.store_temporary_screenshot()
        try:
            element = WebDriverWait(self.browser, 1)\
                .until(EC.element_to_be_clickable((By.XPATH, SELECTOR_SPELLCHECK)))
            element.click()
        except Exception:
            # if there's no spellcheck, ignore
            pass
        self.store_temporary_screenshot()

    def _search_for_product(self, product_name: str):
        try:
            return self._search_for_product_once(product_name)
        except (ElementClickInterceptedException, WebDriverException) as exc:
            if not self._is_retryable_navigation_error(exc) and not isinstance(exc, ElementClickInterceptedException):
                raise
            logger.warning("PhoenixPharma: Retrying product search after transient UI/navigation error: %s", exc)
            self._hide_spellcheck()
            return self._search_for_product_once(product_name)

    def _get_price_header_position(self):
        SELECTOR_PRICE_HEADER_POSITION = "//span[text()='Добави']/ancestor::*[9]//div[starts-with(@id, 'gridcolumn')"\
            + " and "\
            + "@data-ref='titleEl']//span[contains(@data-ref, 'textInnerEl')]"
        table_headers = self.browser.find_elements(By.XPATH, SELECTOR_PRICE_HEADER_POSITION)

        position = 1
        for table_header in table_headers:
            if table_header.get_attribute('innerHTML') == 'Прод.цена с отстъпка':
                return position
            position += 1

        return -1

    def _get_product_price(self, price_header_position):
        SELECTOR_PROD_PRICE = "(//span[text()='Добави']/ancestor::*[9]//td[contains(@class, 'x-grid-cell')])[" + str(price_header_position) + "]//div"
        price_element = WebDriverWait(self.browser, 5)\
            .until(EC.element_to_be_clickable((By.XPATH, SELECTOR_PROD_PRICE)))
        innerHTML = price_element.get_attribute('innerHTML')
        if innerHTML is None:
            return math.inf
        return float(innerHTML.strip().replace("&nbsp;", ""))

    def _get_product_name(self):
        SELECTOR_PROD_NAME = "(//span[text()='Добави']/ancestor::*[9]//td[contains(@class, 'x-grid-cell')])[2]//div"
        name_element = WebDriverWait(self.browser, 5).until(EC.element_to_be_clickable((By.XPATH, SELECTOR_PROD_NAME)))
        product_name = name_element.text.strip().replace("&nbsp;", "")
        product_name = product_name[:product_name.find("\n")+1]
        return product_name

    def get_product_name_and_price(self, productSearchNames: list) -> ScrapedProductInfo:
        logger.info("PhoenixPharma:get_product_name_and_price(): productSearchNames=" + str(productSearchNames))
        element = None
        for productName in productSearchNames:
            try:
                element = self._search_for_product(productName)
            except ElementClickInterceptedException:
                # If the spellcheck caused the miss-click, hide it and retry
                self._hide_spellcheck()
                element = self._search_for_product(productName)

            if element is None:
                continue

            # item found
            price_header_position = self._get_price_header_position()
            if price_header_position == -1:
                logger.error("PhoenixPharma: Price header position was not found...")
                return ScrapedProductInfo(
                    name="",
                    price=math.inf,
                    is_on_promotion=False,
                    alternative_names=None
                )

            return ScrapedProductInfo(
                name=self._get_product_name(),
                price=self._get_product_price(price_header_position),
                is_on_promotion=False,
                alternative_names=None
            )

        return ScrapedProductInfo(
            name="",
            price=math.inf,
            is_on_promotion=False,
            alternative_names=None
        )

    def add_product_to_cart(self, quantity):
        logger.info("PhoenixPharma:add_product_to_cart(): quantity=" + str(quantity))
        plus_button = self.browser.find_element(By.XPATH, self.PRODUCT_PLUS_BUTTON_XPATH)
        for i in range(0, quantity):
            plus_button.click()

        self.store_temporary_screenshot()
        self.browser.find_element(By.XPATH, "//span[text()='Добави']").click()

        self.refresh_page()

        return True

    def _clearSearchResult(self):
        # no need to clear the search if it's already cleared
        if self.lastSearchWasEmpty is True:
            return

        self.lastSearchWasEmpty = True

        logger.info("PhoenixPharma:_clearSearchResult() - clearing last result")
        self.store_temporary_screenshot()
        self._hide_spellcheck()
        search_box = WebDriverWait(self.browser, 10).until(EC.element_to_be_clickable((By.XPATH, self.SEARCH_BOX_XPATH)))
        search_box.clear()

    def refresh_page(self):
        self.browser.refresh()
        try:
            self.store_temporary_screenshot()
            WebDriverWait(self.browser, 2).until(EC.element_to_be_clickable((By.XPATH, "//span[contains(text(), 'Поръчка')]"))).click()
            self.store_temporary_screenshot()
            WebDriverWait(self.browser, 2).until(EC.element_to_be_clickable((By.XPATH, "//span[contains(text(), 'Списък поръчки')]"))).click()
            # select latest order
            SELECTOR_LATEST_ORDER = "//div[@class='x-grid-item-container']//table[1]//td[contains(@class, 'x-grid-cell')][1]"
            self.store_temporary_screenshot()
            WebDriverWait(self.browser, 2).until(EC.element_to_be_clickable((By.XPATH, SELECTOR_LATEST_ORDER))).click()
        except Exception:
            # if self.hasInternetConnection() == False:
            self.refresh_page()
