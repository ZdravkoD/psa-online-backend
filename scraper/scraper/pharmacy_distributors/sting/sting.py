import logging
import math
import time
from typing import Tuple

from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from pharmacy_distributors.common.browser_common import BrowserCommon
from configuration.common import DistributorConfig

SELECTOR_CLEAR_CART = "//tfoot//div[contains(text(), 'Изчисти количката')]"
# Create a logger for this module
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# -*- coding: utf-8 -*-


class StingPharma(BrowserCommon):

    def __init__(self, pharmacyID: str):
        logger.info("StingPharma.__init__()")

        super().__init__("Sting", 10)

        self.LOGIN_PAGE = 'http://web.stingpharma.com/'

        for credential in DistributorConfig.Sting.CONFIG.get_all_users():
            if pharmacyID == credential.id:
                self.user = credential.username
                self.password = credential.password
                break
        else:
            raise ValueError("Pharmacy ID not found in StingPharma config")

        self.SEARCH_BOX_XPATH = "//input[starts-with(@value, 'Име на Артикул')]"
        self.SEARCH_BUTTON_XPATH = "//input[contains(@title, 'Търси')]"

        self.lastSearchWasEmpty = True

    def login(self):
        self.browser.get(self.LOGIN_PAGE)
        self.browser.find_element(
            By.CSS_SELECTOR, "input[id='Login1_UserName']").send_keys(self.user)
        self.browser.find_element(
            By.CSS_SELECTOR, "input[id='Login1_Password']").send_keys(self.password)
        self.browser.find_element(
            By.CSS_SELECTOR, "input[id='Login1_Password']").send_keys(Keys.RETURN)

    def clearCart(self):
        self.store_temporary_screenshot()
        try:
            WebDriverWait(self.browser, 2).until(
                EC.element_to_be_clickable((By.XPATH, SELECTOR_CLEAR_CART))).click()
            alert = self.browser.switch_to.alert
            time.sleep(1)
            alert.accept()
            self.browser.refresh()
        except Exception as e:
            # ignore if cart is already empty
            logger.info("ClearCart error:")
            logger.info(e)

    def prepare_for_order(self):
        self.store_temporary_screenshot()
        # go to Search page
        self.browser.find_element(
            By.CSS_SELECTOR, "li a[href='Users/CartChooseChannel.aspx']").click()
        self.store_temporary_screenshot()
        self.browser.find_element(
            By.CSS_SELECTOR, "td.rcbArrowCell.rcbArrowCellRight").click()
        self.store_temporary_screenshot()
        WebDriverWait(self.browser, 1)\
            .until(EC.element_to_be_clickable((By.XPATH, "//li[contains(text(),'СП-30 дни, БАНКОВ ПРЕВОД')]"))).click()
        self.store_temporary_screenshot()
        self.browser.find_element(
            By.CSS_SELECTOR, "td input[type='image']").click()
        self.clearCart()

        # Change search method to "contains" instead of "starts-with"
        self.store_temporary_screenshot()
        self.browser.find_element(
            By.XPATH, "//input[starts-with(@value, 'започва с')]").click()
        self.store_temporary_screenshot()
        WebDriverWait(self.browser, 2)\
            .until(EC.element_to_be_clickable((By.XPATH, "//ul[@class='rcbList']//li[contains(text(), 'съдържа')]"))).click()

    def _get_price_header_position(self):
        table_headers = self.browser.find_elements(
            By.XPATH, "//table[contains(@id, 'RadGridResult')]//thead//th[not(contains(@style, 'none'))]")

        position = 1
        for table_header in table_headers:
            if table_header.get_attribute('innerHTML') == 'Цена с ТО':
                return position
            position += 1

        return -1

    def _get_name_header_position(self):
        table_headers = self.browser.find_elements(
            By.XPATH, "//table[contains(@id, 'RadGridResult')]//thead//th[not(contains(@style, 'none'))]")

        position = 1
        for table_header in table_headers:
            if table_header.get_attribute('innerHTML') == 'Артикул':
                return position
            position += 1

        return -1

    def _get_product_price(self, price_header_position):
        SELECTOR_PRICE_POSITION = "//table[contains(@id, 'RadGridResult')]//tbody//td[not(contains(@style, 'none'))][" \
            + str(price_header_position) \
            + "]"
        price_element = self.browser.find_element(
            By.XPATH, SELECTOR_PRICE_POSITION)
        innerHTML = price_element.get_attribute('innerHTML')
        if innerHTML is None:
            logger.info(f'StingPharma:_get_product_price(): returning: {math.inf}')
            return math.inf
        logger.info(f'StingPharma:_get_product_price(): returning: {float(innerHTML.strip().replace("&nbsp;", ""))}')
        return float(innerHTML.strip().replace("&nbsp;", ""))

    def _get_product_name(self, name_header_position):
        name_element = self.browser.find_element(
            By.XPATH, "(//table[contains(@id, 'RadGridResult')]//tbody//td[not(contains(@style, 'none'))])[3]")

        product_name = name_element.text.strip().replace("&nbsp;", "")
        logger.info(
            "StingPharma:_get_product_name(): returning: " + product_name)
        return product_name

    def _search_for_product(self, product_name: str):
        logger.info(
            "StingPharma:_search_for_product(): product_name:" + product_name)
        self._clearSearchResult()
        self.browser.find_element(By.XPATH, self.SEARCH_BOX_XPATH).clear()
        self.browser.find_element(
            By.XPATH, self.SEARCH_BOX_XPATH).send_keys(product_name)
        self.store_temporary_screenshot()
        self.browser.find_element(By.XPATH, self.SEARCH_BUTTON_XPATH).click()
        # wait for spinner to appear
        try:
            logger.info(
                "StingPharma:_search_for_product(): Waiting for spinner to appear...")
            WebDriverWait(self.browser, 2).until(EC.element_to_be_clickable(
                (By.CSS_SELECTOR, "body > .RadAjax.RadAjax_Vista")))
        except Exception:
            logger.info(
                "StingPharma:_search_for_product(): Spinner didn't appear, assume it's OK")
        # wait for spinner to dissapear
        logger.info(
            "StingPharma:_search_for_product(): Waiting for spinner to disappear...")
        try:
            WebDriverWait(self.browser, 10).until_not(EC.element_to_be_clickable(
                (By.CSS_SELECTOR, "body > .RadAjax.RadAjax_Vista")))
            time.sleep(0.3)
        except Exception:
            logger.info(
                "StingPharma:_search_for_product(): Spinner didn't disappear, assume it's OK")

        SELECTOR_ADD_QUANTITY = "//div[contains(text(), 'Няма открити артикули.')]|//input[starts-with(@title, 'Добави количеството')]"
        try:
            element = WebDriverWait(self.browser, 5)\
                .until(EC.element_to_be_clickable((By.XPATH, SELECTOR_ADD_QUANTITY)))
        except Exception as e:
            logger.error(
                "StingPharma: Something went wrong with the search result. Didn't get result in less than 5 seconds")
            logger.error(e)
            return None

        number_of_results = len(self.browser.find_elements(
            By.XPATH, SELECTOR_ADD_QUANTITY))
        if number_of_results > 1:
            self.lastSearchWasEmpty = False
            logger.error(
                "StingPharma: Too many results were found with the search. For now, we parse this as an invalid search result")
            return None

        if element.tag_name != 'input':
            return None

        logger.info(
            "StingPharma:_search_for_product(): Found product " + product_name)
        self.lastSearchWasEmpty = False
        return element

    def _clearSearchResult(self):
        # no need to clear the search if it's already cleared
        if self.lastSearchWasEmpty is True:
            return

        self.lastSearchWasEmpty = True
        logger.info("StingPharma:_clearSearchResult() - clearing last result")
        self.browser.find_element(By.XPATH, self.SEARCH_BOX_XPATH).clear()
        self.browser.find_element(
            By.XPATH, self.SEARCH_BOX_XPATH).send_keys("IMPOSSIBLE_PRODUCT")
        self.store_temporary_screenshot()
        self.browser.find_element(By.XPATH, self.SEARCH_BUTTON_XPATH).click()
        # wait for spinner to appear
        try:
            logger.info(
                "StingPharma:_clearSearchResult(): Waiting for spinner to appear...")
            WebDriverWait(self.browser, 2).until(EC.element_to_be_clickable(
                (By.CSS_SELECTOR, "body > .RadAjax.RadAjax_Vista")))
            logger.info(
                "StingPharma:_clearSearchResult(): Waiting for spinner to disappear...")
            WebDriverWait(self.browser, 20).until_not(EC.element_to_be_clickable(
                (By.CSS_SELECTOR, "body > .RadAjax.RadAjax_Vista")))
        except Exception:
            logger.info(
                "StingPharma:_search_for_product(): Spinner didn't appear, return None!")

    def refresh_page(self):
        self.browser.refresh()
        # Change search method to "contains" instead of "starts-with"
        try:
            self.store_temporary_screenshot()
            WebDriverWait(self.browser, 2)\
                .until(EC.element_to_be_clickable((By.XPATH, "//input[starts-with(@value, 'започва с')]"))).click()
            self.store_temporary_screenshot()
            WebDriverWait(self.browser, 2)\
                .until(EC.element_to_be_clickable((By.XPATH, "//ul[@class='rcbList']//li[contains(text(), 'съдържа')]"))).click()
        except Exception:
            # if self.hasInternetConnection() == False:
            self.refresh_page()

    def get_product_name_and_price(self, productSearchNames: list) -> Tuple[str, float]:
        for productName in productSearchNames:
            logger.info(
                "StingPharma.get_product_name_and_price(): Searching for product: '" + productName + "'...")
            element = self._search_for_product(productName)
            if element is None:
                continue

            # item found
            price_header_position = self._get_price_header_position()
            if price_header_position == -1:
                logger.error(
                    "StingPharma: Price header position was not found...")
                return "", math.inf
            name_header_position = self._get_name_header_position()

            return self._get_product_name(name_header_position), self._get_product_price(price_header_position)

        return "", math.inf

    def add_product_to_cart(self, __product_name: str, quantity: int):
        self.browser.find_element(
            By.XPATH, "//td//input[contains(@id, 'QtyResults') and contains(@type, 'text')]").clear()
        self.browser.find_element(
            By.XPATH, "//td//input[contains(@id, 'QtyResults') and contains(@type, 'text')]").send_keys(str(quantity))
        self.store_temporary_screenshot()
        self.browser.find_element(
            By.XPATH, "//input[starts-with(@title, 'Добави количеството')]").click()

        self.refresh_page()

        return True
