import logging
import math
import html
import json
import re
import time
from typing import Optional, Tuple

import requests
from pharmacy_distributors.common.models import ScrapedProductInfo
from selenium.common.exceptions import ElementClickInterceptedException, StaleElementReferenceException, TimeoutException, WebDriverException
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.remote.webelement import WebElement

from pharmacy_distributors.common.browser_common import BrowserCommon
from configuration.common import DistributorConfig

SELECTOR_CLEAR_CART = "//tfoot//div[contains(text(), 'Изчисти количката')]"
# Create a logger for this module
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# -*- coding: utf-8 -*-


class StingPharma(BrowserCommon):
    REQUEST_TIMEOUT_SECONDS = 30
    PREPARE_RETRY_DELAY_SECONDS = 0.2
    POSTBACK_SEARCH_ATTEMPTS = 2
    POSTBACK_SEARCH_RETRY_DELAY_SECONDS = 0.1
    ADD_TO_CART_ATTEMPTS = 3
    ADD_TO_CART_RETRY_DELAY_SECONDS = 0.1

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
        self._postback_form_state: dict[str, str] | None = None
        self._last_search_result_name: str | None = None

    def login(self):
        self.remember_action("Opening Sting login page")
        self.open_url(self.LOGIN_PAGE, retries=3)
        self.remember_action(f"Entering Sting username for pharmacy {self.user}")
        self.browser.find_element(
            By.CSS_SELECTOR, "input[id='Login1_UserName']").send_keys(self.user)
        self.remember_action("Submitting Sting login form")
        self.browser.find_element(
            By.CSS_SELECTOR, "input[id='Login1_Password']").send_keys(self.password)
        self.browser.find_element(
            By.CSS_SELECTOR, "input[id='Login1_Password']").send_keys(Keys.RETURN)

    def clearCart(self):
        self.remember_action("Clearing Sting cart")
        self.store_temporary_screenshot()
        try:
            WebDriverWait(self.browser, 2).until(
                EC.element_to_be_clickable((By.XPATH, SELECTOR_CLEAR_CART))).click()
            alert = WebDriverWait(self.browser, 2).until(EC.alert_is_present())
            alert.accept()
            self.browser.refresh()
        except Exception as e:
            # ignore if cart is already empty
            logger.info("ClearCart error:")
            logger.info(e)

    def prepare_for_order(self):
        try:
            self._prepare_for_order_once()
        except (TimeoutException, WebDriverException) as exc:
            if not self._is_retryable_navigation_error(exc):
                raise
            logger.warning("StingPharma: Retrying prepare_for_order after transient navigation error: %s", exc)
            time.sleep(self.PREPARE_RETRY_DELAY_SECONDS)
            self._prepare_for_order_once()

    def _prepare_for_order_once(self):
        self.store_temporary_screenshot()
        self.remember_action("Navigating to Sting channel selection")
        # go to Search page
        self.browser.find_element(
            By.CSS_SELECTOR, "li a[href='Users/CartChooseChannel.aspx']").click()
        self.store_temporary_screenshot()
        self.remember_action("Opening Sting channel dropdown")
        self.browser.find_element(
            By.CSS_SELECTOR, "td.rcbArrowCell.rcbArrowCellRight").click()
        self.store_temporary_screenshot()
        self.remember_action("Selecting Sting payment channel")
        WebDriverWait(self.browser, 1)\
            .until(EC.element_to_be_clickable((By.XPATH, "//li[contains(text(),'СП-30 дни, БАНКОВ ПРЕВОД')]"))).click()
        self.store_temporary_screenshot()
        self.remember_action("Confirming Sting channel selection")
        self.browser.find_element(
            By.CSS_SELECTOR, "td input[type='image']").click()
        self.clearCart()

        # Change search method to "contains" instead of "starts-with"
        self.store_temporary_screenshot()
        self.remember_action("Opening Sting search mode selector")
        self.browser.find_element(
            By.XPATH, "//input[starts-with(@value, 'започва с')]").click()
        self.store_temporary_screenshot()
        self.remember_action("Switching Sting search mode to contains")
        WebDriverWait(self.browser, 2)\
            .until(EC.element_to_be_clickable((By.XPATH, "//ul[@class='rcbList']//li[contains(text(), 'съдържа')]"))).click()

    def _get_price_header_position(self):
        table_headers = self.browser.find_elements(
            By.XPATH, "//table[contains(@id, 'RadGridResult')]//thead//th[not(contains(@style, 'none'))]")

        position = 1
        for table_header in table_headers:
            inner_html = table_header.get_attribute('textContent')
            if inner_html is not None and inner_html.strip() == 'Цена с ТО €':
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

    def _get_is_product_in_promotion(self):
        name_element = self.browser.find_element(
            By.XPATH, "(//table[contains(@id, 'RadGridResult')]//tbody//td[not(contains(@style, 'none'))])[3]")
        try:
            star_element = name_element.find_element(By.XPATH, '//input[contains(@id, "PromoOpener")]')
        except Exception:
            return False

        return star_element is not None

    def _build_requests_session(self) -> requests.Session:
        session = requests.Session()
        for cookie in self.browser.get_cookies():
            session.cookies.set(
                cookie["name"],
                cookie["value"],
                domain=cookie.get("domain"),
                path=cookie.get("path"),
            )
        return session

    def _capture_postback_form_state_from_browser(self) -> dict[str, str]:
        state: dict[str, str] = {}
        for element in self.browser.find_elements(By.XPATH, "//input[@name]"):
            name = element.get_attribute("name") or ""
            if name == "":
                continue
            input_type = (element.get_attribute("type") or "").lower()
            if not self._is_reusable_postback_state_field(name, input_type):
                continue
            state[name] = element.get_attribute("value") or ""
        return state

    def _is_reusable_postback_state_field(self, field_name: str, input_type: str) -> bool:
        lowered_field_name = field_name.lower()
        if "radgrid" in lowered_field_name or "qtyresults" in lowered_field_name:
            return False
        if input_type == "hidden":
            return True
        if "radcomboboxsearchtype" in lowered_field_name:
            return True
        if field_name == self._get_name_filter_box_field_name():
            return True
        if field_name == self._get_name_filter_box_client_state_field_name():
            return True
        return False

    def _get_postback_form_state(self) -> dict[str, str]:
        if self._postback_form_state is None:
            self._postback_form_state = self._capture_postback_form_state_from_browser()
        return {
            field_name: value
            for field_name, value in self._postback_form_state.items()
            if self._is_reusable_postback_state_field(field_name, "hidden")
        }

    def _update_postback_form_state(self, response_text: str, product_name: str):
        if self._postback_form_state is None:
            self._postback_form_state = {}

        self._postback_form_state[self._get_name_filter_box_field_name()] = product_name
        self._postback_form_state[self._get_name_filter_box_client_state_field_name()] = json.dumps(
            {
                "enabled": True,
                "emptyMessage": "Име на Артикул / Генерика / Код НЗОК",
                "validationText": product_name,
                "valueAsString": product_name,
                "lastSetTextBoxValue": product_name,
            },
            ensure_ascii=False,
            separators=(",", ":"),
        )

        for field_name, value in re.findall(r"hiddenField\|([^|]+)\|([^|]*)", response_text):
            if self._is_reusable_postback_state_field(field_name, "hidden"):
                self._postback_form_state[field_name] = value

    def _get_search_button_field_name(self) -> str:
        return (
            "ctl00$ctl00$ctl00$ctl00$ctl00$ContentPlaceHolderBody$ContentPlaceHolderBody$"
            "ContentPlaceHolderBody$ContentPlaceHolderBody$ContentPlaceHolderBody$SearchButton"
        )

    def _get_rad_script_manager_field_name(self) -> str:
        return "ctl00$ctl00$ctl00$ctl00$ctl00$RadScriptManager1"

    def _get_name_filter_box_field_name(self) -> str:
        return (
            "ctl00$ctl00$ctl00$ctl00$ctl00$ContentPlaceHolderBody$ContentPlaceHolderBody$"
            "ContentPlaceHolderBody$ContentPlaceHolderBody$ContentPlaceHolderBody$NameFilterBox"
        )

    def _get_name_filter_box_client_state_field_name(self) -> str:
        return (
            "ctl00_ctl00_ctl00_ctl00_ctl00_ContentPlaceHolderBody_ContentPlaceHolderBody_"
            "ContentPlaceHolderBody_ContentPlaceHolderBody_ContentPlaceHolderBody_NameFilterBox_ClientState"
        )

    def _build_search_postback_payload(self, product_name: str) -> dict[str, str]:
        payload = self._get_postback_form_state()
        search_button_name = self._get_search_button_field_name()
        payload[self._get_rad_script_manager_field_name()] = (
            f"{self._get_rad_script_manager_field_name()}|{search_button_name}"
        )
        payload[self._get_name_filter_box_field_name()] = product_name
        payload[self._get_name_filter_box_client_state_field_name()] = json.dumps(
            {
                "enabled": True,
                "emptyMessage": "Име на Артикул / Генерика / Код НЗОК",
                "validationText": product_name,
                "valueAsString": product_name,
                "lastSetTextBoxValue": product_name,
            },
            ensure_ascii=False,
            separators=(",", ":"),
        )
        payload["__ASYNCPOST"] = "true"
        payload[f"{search_button_name}.x"] = "12"
        payload[f"{search_button_name}.y"] = "12"
        return payload

    def _search_for_product_via_postback(self, product_name: str) -> Tuple[Optional[dict], Optional[list[str]]]:
        last_error = None
        for attempt in range(1, self.POSTBACK_SEARCH_ATTEMPTS + 1):
            self.remember_action(f"Searching Sting for product '{product_name}' via postback")
            try:
                self._wait_until_ajax_overlay_is_gone()
                current_url = self.browser.current_url
                user_agent = self.browser.execute_script("return navigator.userAgent")
                response = self._build_requests_session().post(
                    current_url,
                    data=self._build_search_postback_payload(product_name),
                    headers={
                        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                        "X-MicrosoftAjax": "Delta=true",
                        "X-Requested-With": "XMLHttpRequest",
                        "Referer": current_url,
                        "Origin": "https://web.stingpharma.com",
                        "User-Agent": user_agent,
                    },
                    timeout=self.REQUEST_TIMEOUT_SECONDS,
                )
                response.raise_for_status()
                self._update_postback_form_state(response.text, product_name)

                parsed_rows = self._parse_search_results_panel_html(response.text)
                if parsed_rows is None:
                    raise ValueError("StingPharma: Could not parse Sting postback search response")

                if len(parsed_rows) == 0:
                    self.lastSearchWasEmpty = True
                    return None, None

                if len(parsed_rows) > 1:
                    self.lastSearchWasEmpty = False
                    return None, [row["name"] for row in parsed_rows]

                self.lastSearchWasEmpty = False
                return parsed_rows[0], None
            except StaleElementReferenceException as exc:
                last_error = exc
                if attempt != self.POSTBACK_SEARCH_ATTEMPTS:
                    time.sleep(self.POSTBACK_SEARCH_RETRY_DELAY_SECONDS)
                    continue
                raise

        raise last_error if last_error is not None else ValueError("StingPharma: Postback search failed unexpectedly")

    def _extract_results_panel_html(self, response_text: str) -> Optional[str]:
        match = re.search(
            r"updatePanel\|[^|]*RadGridResultsPanel\|(.*?)\|\d+\|(?:updatePanel|hiddenField|scriptBlock|onSubmit|asyncPostBackControlIDs)\|",
            response_text,
            re.S,
        )
        if match is None:
            return None
        return match.group(1)

    def _strip_html_text(self, value: str) -> str:
        without_tags = re.sub(r"<[^>]+>", "", value)
        normalized = html.unescape(without_tags).replace("\xa0", " ")
        return re.sub(r"\s+", " ", normalized).strip()

    def _parse_search_results_panel_html(self, response_text: str) -> Optional[list[dict]]:
        panel_html = self._extract_results_panel_html(response_text)
        if panel_html is None:
            return None

        if "Няма открити артикули." in panel_html:
            return []

        header_matches = re.findall(r"<th\b([^>]*)>(.*?)</th>", panel_html, re.S)
        visible_headers: list[str] = []
        for attrs, content in header_matches:
            if "display:none" in attrs.replace(" ", ""):
                continue
            visible_headers.append(self._strip_html_text(content))

        if len(visible_headers) == 0:
            return None

        rows: list[dict] = []
        for row_html in re.findall(r"<tr class=\"rg(?:Row|AltRow)\".*?</tr>", panel_html, re.S):
            cell_matches = re.findall(r"<td\b([^>]*)>(.*?)</td>", row_html, re.S)
            visible_cells: list[str] = []
            raw_cells: list[tuple[str, str]] = []
            for attrs, content in cell_matches:
                raw_cells.append((attrs, content))
                if "display:none" in attrs.replace(" ", ""):
                    continue
                visible_cells.append(self._strip_html_text(content))

            if len(visible_cells) != len(visible_headers):
                continue

            row_data = dict(zip(visible_headers, visible_cells))
            price_text = row_data.get("Цена с ТО €", "")
            if price_text == "":
                continue

            rows.append(
                {
                    "name": row_data.get("Артикул", ""),
                    "price": float(price_text.replace(",", ".")),
                    "is_on_promotion": "PromoOpener" in row_html,
                    "has_add_input": any("QtyResults" in content for _, content in raw_cells),
                }
            )

        return rows

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

    def _wait_until_ajax_overlay_is_gone(self, timeout: float = 1.0, poll_frequency: float = 0.05):
        def overlay_is_gone(_browser):
            try:
                overlays = _browser.find_elements(By.CSS_SELECTOR, "div.raDiv")
            except StaleElementReferenceException:
                return False

            for overlay in overlays:
                try:
                    if overlay.is_displayed():
                        return False
                except StaleElementReferenceException:
                    return False
            return True

        WebDriverWait(self.browser, timeout, poll_frequency=poll_frequency).until(overlay_is_gone)

    def _restore_search_state_after_add(self):
        WebDriverWait(self.browser, 2, poll_frequency=0.1).until(
            EC.element_to_be_clickable((By.XPATH, self.SEARCH_BOX_XPATH))
        )

        search_mode_inputs = self.browser.find_elements(By.XPATH, "//input[starts-with(@value, 'започва с')]")
        if len(search_mode_inputs) > 0:
            search_mode_inputs[0].click()
            WebDriverWait(self.browser, 1, poll_frequency=0.1).until(
                EC.element_to_be_clickable((By.XPATH, "//ul[@class='rcbList']//li[contains(text(), 'съдържа')]"))
            ).click()
        self._postback_form_state = None

    def _submit_add_to_cart(self, quantity: int):
        quantity_xpath = "//td//input[contains(@id, 'QtyResults') and contains(@type, 'text')]"
        add_button_xpath = "//input[starts-with(@title, 'Добави количеството')]"
        last_error = None

        for attempt in range(1, self.ADD_TO_CART_ATTEMPTS + 1):
            try:
                self._wait_until_ajax_overlay_is_gone()
                quantity_input = self._wait_for_interactable_xpath(quantity_xpath, timeout=2)
                quantity_input.clear()
                quantity_input.send_keys(str(quantity))
                self.store_temporary_screenshot()
                self._wait_until_ajax_overlay_is_gone()
                self._wait_for_interactable_xpath(add_button_xpath, timeout=2).click()
                return
            except (ElementClickInterceptedException, StaleElementReferenceException, TimeoutException) as exc:
                last_error = exc
                if attempt != self.ADD_TO_CART_ATTEMPTS:
                    time.sleep(self.ADD_TO_CART_RETRY_DELAY_SECONDS)

        if last_error is not None:
            raise last_error

    def _search_for_product(self, product_name: str) -> Tuple[Optional[WebElement], Optional[list[str]]]:
        logger.info(
            "StingPharma:_search_for_product(): product_name:" + product_name)
        self.remember_action(f"Searching Sting for product '{product_name}'")
        self._clearSearchResult()
        self.browser.find_element(By.XPATH, self.SEARCH_BOX_XPATH).clear()
        self.browser.find_element(
            By.XPATH, self.SEARCH_BOX_XPATH).send_keys(product_name)
        self.store_temporary_screenshot()
        self.browser.find_element(By.XPATH, self.SEARCH_BUTTON_XPATH).click()

        SELECTOR_ADD_QUANTITY = "//div[contains(text(), 'Няма открити артикули.')]|//input[starts-with(@title, 'Добави количеството')]"
        try:
            element: WebElement = self._wait_for_interactable_xpath(SELECTOR_ADD_QUANTITY, timeout=3)
        except Exception as e:
            logger.error(
                "StingPharma: Something went wrong with the search result. Didn't get result in less than 3 seconds")
            logger.error(e)
            return None, None

        number_of_results = len(self.browser.find_elements(
            By.XPATH, SELECTOR_ADD_QUANTITY))
        if number_of_results > 1:
            self.lastSearchWasEmpty = False
            logger.info(
                "StingPharma: Too many results were found with the search. For now, we parse this as an invalid search result, but we add the alternative names to the result")

            # select all rows with xpath
            # then select the first td element in each row
            # then get the text of the element
            # then strip the text
            # then add the text to the list
            try:
                alternative_names = [element.text.strip() for element in self.browser.find_elements(
                    By.XPATH, "//table[contains(@id, 'RadGridResult')]//tbody//tr[contains(@class, 'rgRow') or contains(@class, 'rgAltRow')]/td[not(@style='display:none;')][1]")]
            except Exception as e:
                logger.error(
                    "StingPharma: Couldn't get alternative names from the search result")
                logger.error(e)
                return None, None

            return None, alternative_names

        if element.tag_name != 'input':
            return None, None

        logger.info(
            "StingPharma:_search_for_product(): Found product " + product_name)
        self.lastSearchWasEmpty = False
        self._last_search_result_name = product_name
        return element, None

    def _clearSearchResult(self):
        # no need to clear the search if it's already cleared
        if self.lastSearchWasEmpty is True:
            return

        self.lastSearchWasEmpty = True
        self.remember_action("Clearing previous Sting search results")
        logger.info("StingPharma:_clearSearchResult() - clearing last result")
        self.browser.find_element(By.XPATH, self.SEARCH_BOX_XPATH).clear()
        self.store_temporary_screenshot()
        self._last_search_result_name = None

    def refresh_page(self):
        self.remember_action("Refreshing Sting product page")
        self.browser.refresh()
        # Change search method to "contains" instead of "starts-with"
        try:
            self.store_temporary_screenshot()
            self.remember_action("Reopening Sting search mode selector after refresh")
            WebDriverWait(self.browser, 2)\
                .until(EC.element_to_be_clickable((By.XPATH, "//input[starts-with(@value, 'започва с')]"))).click()
            self.store_temporary_screenshot()
            self.remember_action("Restoring Sting search mode to contains after refresh")
            WebDriverWait(self.browser, 2)\
                .until(EC.element_to_be_clickable((By.XPATH, "//ul[@class='rcbList']//li[contains(text(), 'съдържа')]"))).click()
        except Exception:
            # if self.hasInternetConnection() == False:
            self.refresh_page()

    def get_product_name_and_price(self, productSearchNames: list) -> ScrapedProductInfo:
        all_alternative_names = []
        for productName in productSearchNames:
            logger.info(
                "StingPharma.get_product_name_and_price(): Searching for product: '" + productName + "'...")
            try:
                parsed_row, alternative_names = self._search_for_product_via_postback(productName)
                if parsed_row is not None:
                    self._last_search_result_name = None
                    return ScrapedProductInfo(
                        name=parsed_row["name"],
                        price=parsed_row["price"],
                        is_on_promotion=parsed_row["is_on_promotion"],
                        alternative_names=all_alternative_names if len(all_alternative_names) > 0 else None
                    )
                if alternative_names is not None:
                    all_alternative_names.extend(alternative_names)
                continue
            except Exception as exc:
                logger.warning("StingPharma: Postback search failed for '%s', falling back to UI flow: %s", productName, exc)
                self.refresh_page()
                self._postback_form_state = None
                self._last_search_result_name = None

            element, alternative_names = self._search_for_product(productName)
            if alternative_names is not None:
                all_alternative_names.extend(alternative_names)
            if element is None:
                continue

            # item found
            price_header_position = self._get_price_header_position()
            if price_header_position == -1:
                logger.error(
                    "StingPharma: Price header position was not found...")
                return ScrapedProductInfo(
                    name="",
                    price=math.inf,
                    is_on_promotion=False,
                    alternative_names=all_alternative_names if len(all_alternative_names) > 0 else None
                )
            name_header_position = self._get_name_header_position()

            return ScrapedProductInfo(
                name=self._get_product_name(name_header_position),
                price=self._get_product_price(price_header_position),
                is_on_promotion=self._get_is_product_in_promotion(),
                alternative_names=all_alternative_names if len(all_alternative_names) > 0 else None
            )

        return ScrapedProductInfo(
            name="",
            price=math.inf,
            is_on_promotion=False,
            alternative_names=all_alternative_names if len(all_alternative_names) > 0 else None
        )

    def add_product_to_cart(self, __product_name: str, quantity: int):
        if self._last_search_result_name != __product_name:
            element, _ = self._search_for_product(__product_name)
            if element is None:
                return False
        self.remember_action(f"Adding product to Sting cart with quantity {quantity}")
        self._submit_add_to_cart(quantity)

        try:
            self._restore_search_state_after_add()
        except Exception as exc:
            logger.warning("StingPharma: Fast search state restore failed after add-to-cart, falling back to refresh: %s", exc)
            self.refresh_page()
            self._postback_form_state = None
        self._last_search_result_name = None

        return True
