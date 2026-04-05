import logging
import math
import re
from typing import Optional, Tuple
from urllib.parse import quote
import requests
import xmltodict
from pharmacy_distributors.common.models import ScrapedProductInfo
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webelement import WebElement

from pharmacy_distributors.phoenix.phoenix import PhoenixPharma

# Create a logger for this module
logger = logging.getLogger(__name__)

# -*- coding: utf-8 -*-


class PhoenixPharmaOptimized(PhoenixPharma):

    def __init__(self, pharmacyID: str, shouldInitBrowser=True):
        super().__init__(pharmacyID, shouldInitBrowser)

        self.pharmacyID = pharmacyID

    def _get_json_result_of_search(self, product_name: str):
        php_session_id_cookie = self.browser.get_cookie("PHPSESSID")
        if php_session_id_cookie is None:
            logger.error("PhoenixPharma: PHPSESSID cookie is missing...")
            return None
        http_response = requests.get("https://b2b.phoenixpharma.bg/bg/build/production/BgShop/resources/php/combo/article.php?selby=article&" +
                                     "query=" + quote(product_name) +
                                     "&order_type=F" +
                                     "&order_partner_id=4695" +
                                     "&mode=name_inside",
                                     headers={"Cookie": "PHPSESSID=" + str(php_session_id_cookie["value"])})
        json_root = xmltodict.parse(http_response.text)
        return json_root

    # returns name and price
    # order_type + order_partner_id => These parameters are allowing us to get the discount price. All of them are hardcoded
    def _search_for_product_optimized(self, product_name: str) -> Tuple[Optional[str], Optional[float], Optional[list[str]]]:
        self.remember_action(f"Searching Phoenix for product '{product_name}' via optimized endpoint")
        logger.info("PhoenixPharma._search_for_product_optimized(): Searching for product: '" + product_name + "'...")
        json_root = self._get_json_result_of_search(product_name)
        if json_root is None:
            logger.error("PhoenixPharma._search_for_product_optimized(): Search result is empty...")
            return None, None, None
        number_of_results = int(json_root["dataset"]["results"])

        logger.info("PhoenixPharmaOptimized: number_of_results=" + str(number_of_results))
        if number_of_results == 0:
            logger.error("PhoenixPharma._search_for_product_optimized(): Search result is empty...")
            return None, None, None
        if number_of_results > 1:
            self.lastSearchWasEmpty = False
            alternative_names = []
            filtered_rows = [row for row in json_root["dataset"]["row"] if row.get("ExpiryDate") and row.get("isWebSaleProhibition") == '0']
            if len(filtered_rows) == 0:
                logger.error("PhoenixPharma: Found multiple products with search, but none of them have an expiry date, so we're skipping these products...")
                return None, None, None
            elif len(filtered_rows) > 1:
                logger.error("PhoenixPharma: Found multiple products with search, but more than one of them have an expiry date, so we're skipping these products and we add the product names to the alternative names...")
                for row in filtered_rows:
                    alternative_names.append(row["CyrName"])
                return None, None, alternative_names
            else:
                # We have only one product with expiry date, so we return it
                logger.info("PhoenixPharma: Found multiple products with search, but only one of them has an expiry date, so we're returning this product...")
                json_root["dataset"]["row"] = filtered_rows[0]

        result_product_expiry_date = json_root["dataset"]["row"]["ExpiryDate"]
        if result_product_expiry_date is None or result_product_expiry_date.strip() == "":
            self.lastSearchWasEmpty = False
            logger.error("PhoenixPharma: Found product with search, but the expiry date was empty, so we're skipping this product...")
            # TODO: Do not return none for alternative names
            return None, None, None

        if json_root['dataset']['row']['isWebSaleProhibition'] != '0':
            logger.error(
                f"PhoenixPharma: Found product with search, but the product is not available for web sale, so we're skipping this product...: isWebSaleProhibition={json_root['dataset']['row']['isWebSaleProhibition']}")
            return None, None, None

        result_product_name = json_root["dataset"]["row"]["CyrName"]
        result_product_price = float(json_root["dataset"]["row"]["pdPrice"])

        logger.info("PhoenixPharma:_search_for_product_optimized(): Found product "
                    + result_product_name
                    + ", with price: " + str(result_product_price)
                    + ", and ExpiryDate: " + result_product_expiry_date)
        self.lastSearchWasEmpty = False
        return result_product_name, result_product_price, None

    def get_product_name_and_price(self, productSearchNames: list) -> ScrapedProductInfo:
        logger.info("PhoenixPharmaOptimized:get_product_name_and_price(): productSearchNames=" + str(productSearchNames))
        all_alternative_names: set[str] = set()
        for productName in productSearchNames:
            result_product_name, result_product_price, alternative_names = self._search_for_product_optimized(productName)
            # add all items from alternative_names to all_alternative_names
            if alternative_names is not None:
                all_alternative_names.update(alternative_names)

            if result_product_name is None:
                continue

            return ScrapedProductInfo(
                name=result_product_name,
                price=result_product_price if result_product_price is not None else math.inf,
                is_on_promotion=False,
                alternative_names=list(all_alternative_names))

        return ScrapedProductInfo(
            name="",
            price=math.inf,
            is_on_promotion=False,
            alternative_names=list(all_alternative_names)
        )

    def _add_product_to_cart_optimized(self, quantity):
        # handle case when multiple products are found and we need to select the one that has an expiry date - "Годност: ..."
        # select all html elements that have a class .x-grid-item
        table_rows = self.browser.find_elements(By.XPATH, "//table[contains(@class, 'x-grid-item')]")
        target_table_row: Optional[WebElement] = None
        # For each table row, check if it contains the expiry date - "Годност: ..."
        for table_row in table_rows:
            try:
                expiry_date_element = table_row.find_element(By.XPATH, ".//span[contains(text(), 'Годност')]")
                if expiry_date_element is not None and self._extract_expiry_date(expiry_date_element) is not None:
                    target_table_row = table_row
                    break
            except Exception as e:
                logger.error("PhoenixPharma: An error occurred while selecting product: %s", str(e))
        if target_table_row is None:
            logger.error("PhoenixPharma::_add_product_to_cart_optimized(): Could not find the target table row with an expiry date...")
            return None

        plus_button = target_table_row.find_element(By.XPATH, self.PRODUCT_PLUS_BUTTON_XPATH)
        actions = ActionChains(self.browser)
        actions.move_to_element(plus_button).perform()
        for i in range(0, quantity):
            plus_button.click()

        self.browser.find_element(By.XPATH, "//span[text()='Добави']").click()

    def _extract_expiry_date(self, product_metadata_element: WebElement) -> Optional[str]:
        # Regular expression to capture the text between "Годност:" and "Произв.:"
        pattern = r'Годност:\s*(.*?)Произв\.'
        # Search for the pattern in the text
        match = re.search(pattern, product_metadata_element.text)
        if match:
            expiry_date = match.group(1)
            print(f"Extracted expiry date: {expiry_date}")
            return expiry_date

        return None

    def add_product_to_cart(self, product_name: str, quantity):
        self.remember_action(f"Adding product '{product_name}' to Phoenix cart with quantity {quantity}")
        logger.info("PhoenixPharmaOptimized: Adding product to cart: " + product_name + ", quantity: " + str(quantity))
        self._search_for_product(product_name)

        try:
            self._add_product_to_cart_optimized(quantity)
        except Exception as e:
            if self._is_retryable_navigation_error(e):
                logger.warning("PhoenixPharma: Retrying add-to-cart after navigation error: %s", str(e))
                self.refresh_page()
                self._search_for_product(product_name)
                self._add_product_to_cart_optimized(quantity)
                return True
            logger.error("PhoenixPharma: An error occurred while adding product to cart: %s", str(e))
            close_buttons = self.browser.find_elements(By.XPATH, "//div[contains(@data-qtip,'Close dialog')]")
            for close_button in close_buttons:
                try:
                    close_button.click()
                    break
                except Exception as e_inner:
                    logger.error("PhoenixPharma: An error occurred while closing dialog: %s", str(e_inner))
                    return None

            self._add_product_to_cart_optimized(quantity)

        return True
