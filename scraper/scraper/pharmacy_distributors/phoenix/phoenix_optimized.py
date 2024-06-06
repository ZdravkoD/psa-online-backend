import logging
import math
from urllib.parse import quote
import requests
import xmltodict
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By

from pharmacy_distributors.phoenix.phoenix import PhoenixPharma


# -*- coding: utf-8 -*-


class PhoenixPharmaOptimized(PhoenixPharma):

    def __init__(self, pharmacyID: str, shouldInitBrowser=True):
        super().__init__(pharmacyID, shouldInitBrowser)

        self.pharmacyID = pharmacyID

    def _get_json_result_of_search(self, product_name: str):
        php_session_id_cookie = self.browser.get_cookie("PHPSESSID")
        if php_session_id_cookie is None:
            logging.error("PhoenixPharma: PHPSESSID cookie is missing...")
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
    def _search_for_product_optimized(self, product_name: str):
        print("PhoenixPharma._search_for_product_optimized(): Searching for product: '" + product_name + "'...")
        json_root = self._get_json_result_of_search(product_name)
        if json_root is None:
            logging.error("PhoenixPharma._search_for_product_optimized(): Search result is empty...")
            return None, None
        number_of_results = int(json_root["dataset"]["results"])

        print("PhoenixPharmaOptimized: number_of_results=" + str(number_of_results))
        if number_of_results == 0:
            logging.error("PhoenixPharma._search_for_product_optimized(): Search result is empty...")
            return None, None
        if number_of_results > 1:
            self.lastSearchWasEmpty = False
            logging.error("PhoenixPharma: Too many results were found with the search. For now, we parse this as an invalid search result")
            return None, None
        result_product_expiry_date = json_root["dataset"]["row"]["ExpiryDate"]
        if result_product_expiry_date is None or result_product_expiry_date.strip() == "":
            self.lastSearchWasEmpty = False
            logging.error("PhoenixPharma: Found product with search, but the expiry date was empty, so we're skipping this product...")
            return None, None

        result_product_name = json_root["dataset"]["row"]["CyrName"]
        result_product_price = float(json_root["dataset"]["row"]["pdPrice"])

        print("PhoenixPharma:_search_for_product_optimized(): Found product "
              + result_product_name
              + ", with price: " + str(result_product_price)
              + ", and ExpiryDate: " + result_product_expiry_date)
        self.lastSearchWasEmpty = False
        return result_product_name, result_product_price

    def get_product_name_and_price(self, productSearchNames: list):
        print("PhoenixPharmaOptimized:get_product_name_and_price(): productSearchNames=" + str(productSearchNames))
        for productName in productSearchNames:
            result_product_name, result_product_price = self._search_for_product_optimized(productName)

            if result_product_name is None:
                continue

            return result_product_name, result_product_price

        return "", math.inf

    def _add_product_to_cart_optimized(self, quantity):
        plus_button = self.browser.find_element(By.XPATH, self.PRODUCT_PLUS_BUTTON_XPATH)
        actions = ActionChains(self.browser)
        actions.move_to_element(plus_button).perform()
        for i in range(0, quantity):
            plus_button.click()

        self.browser.find_element(By.XPATH, "//span[text()='Добави']").click()

    def add_product_to_cart(self, product_name: str, quantity):
        print("PhoenixPharmaOptimized: Adding product to cart: " + product_name + ", quantity: " + str(quantity))
        self._search_for_product(product_name)

        try:
            self._add_product_to_cart_optimized(quantity)
        except Exception as e:
            logging.error("PhoenixPharma: An error occurred while adding product to cart: %s", str(e))
            close_buttons = self.browser.find_elements(By.XPATH, "//div[contains(@data-qtip,'Close dialog')]")
            for close_button in close_buttons:
                try:
                    close_button.click()
                    break
                except Exception as e_inner:
                    logging.error("PhoenixPharma: An error occurred while closing dialog: %s", str(e_inner))
                    return None

            self._add_product_to_cart_optimized(quantity)

        return True
