import logging
import math
from typing import Tuple

from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import ElementClickInterceptedException

from pharmacy_distributors.common.browser_common import BrowserCommon
from configuration.common import DistributorConfig


SELECTOR_SPELLCHECK = "//div[contains(@data-componentid, 'order-spellcheckwindow')]//div[contains(@class, 'x-tool-tool-el')]"
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

        self.lastSearchWasEmpty = True

    def login(self):
        self.browser.get(self.DUMMY_PAGE)
        self.browser.add_cookie({'name': 'cookiesAsked', 'value': 'true'})
        self.browser.add_cookie({'name': 'cookiesAllowedMarketing', 'value': 'false'})
        self.browser.add_cookie({'name': 'cookiesAllowedAnalytical', 'value': 'false'})
        self.browser.get(self.LOGIN_PAGE)

        self.store_temporary_screenshot()
        self.browser.find_element(By.CSS_SELECTOR, "input[name='loginUsername']").send_keys(self.username)
        self.browser.find_element(By.CSS_SELECTOR, "input[name='loginPasswordText']").click()
        self.browser.find_element(By.CSS_SELECTOR, "input[name='loginPasswordText']").send_keys(self.password)
        self.store_temporary_screenshot()
        self.browser.find_element(By.CSS_SELECTOR, "input[name='loginPasswordText']").send_keys(Keys.RETURN)

    def prepare_for_order(self):
        WebDriverWait(self.browser, 2).until(EC.element_to_be_clickable((By.XPATH, "//span[contains(text(), 'Поръчка')]"))).click()
        self.store_temporary_screenshot()
        self.browser.find_element(By.XPATH, "//span[contains(text(), 'Нова поръчка свободна')]").click()

        self.browser.find_element(By.CSS_SELECTOR, "input[name='order_partner_id']").send_keys(self.pharmacyID)
        try:
            element = WebDriverWait(self.browser, 5)\
                .until(EC.element_to_be_clickable((By.XPATH, "//div[contains(@class, 'x-grid-cell-inner') and text() = '" + self.pharmacyID + "']")))
            element.click()
        except Exception:
            logger.debug("PhoenixPharma:prepare_for_order(): Couldn't find the pharmacy with ID " + self.pharmacyID)
            pass

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
        self._clearSearchResult()
        logger.info("PhoenixPharma:_search_for_product(): product_name:" + product_name)
        self.browser.find_element(By.XPATH, self.SEARCH_BOX_XPATH).clear()
        self.browser.find_element(By.XPATH, self.SEARCH_BOX_XPATH).send_keys(product_name)
        self.store_temporary_screenshot()
        self.browser.find_element(By.CSS_SELECTOR, self.SEARCH_BUTTON_CSS_SELECTOR).click()

        # if spellcheck popup appears, hide it
        try:
            element = WebDriverWait(self.browser, 5)\
                .until(EC.element_to_be_clickable((By.XPATH, SELECTOR_SPELLCHECK + "|" + self.PRODUCT_PLUS_BUTTON_XPATH)))
            if element.tag_name == 'div':
                logger.info("PhoenixPharma: Closing spellcheck")
                # spellcheck is triggered only if there are no results, so return None
                element.click()
                return None
        except Exception:
            # Neither spellcheck nor result was found, so return None
            return None

        number_of_results = len(self.browser.find_elements(By.XPATH, self.PRODUCT_PLUS_BUTTON_XPATH))
        logger.info("PhoenixPharma: number_of_results=" + str(number_of_results))
        if number_of_results == 0:
            logger.error("PhoenixPharma: Search result is empty...")
            return None
        if number_of_results > 1:
            self.lastSearchWasEmpty = False
            logger.error("PhoenixPharma: Too many results were found with the search. For now, we parse this as an invalid search result")
            return None

        logger.info("PhoenixPharma:_search_for_product(): Found product " + product_name)
        self.lastSearchWasEmpty = False
        return element

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

    def get_product_name_and_price(self, productSearchNames: list) -> Tuple[str, float]:
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
                return "", math.inf

            return self._get_product_name(), self._get_product_price(price_header_position)

        return "", math.inf

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

        self.browser.find_element(By.XPATH, self.SEARCH_BOX_XPATH).clear()
        self.browser.find_element(By.XPATH, self.SEARCH_BOX_XPATH).send_keys("IMPOSSIBLE_PRODUCT")
        try:
            self.browser.find_element(By.CSS_SELECTOR, self.SEARCH_BUTTON_CSS_SELECTOR).click()
        except Exception:
            self._hide_spellcheck()
            self.browser.find_element(By.CSS_SELECTOR, self.SEARCH_BUTTON_CSS_SELECTOR).click()

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
