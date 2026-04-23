import html
import json
import logging
import math
import time
from datetime import datetime
from typing import Any, Optional, Tuple
from urllib.parse import quote
from xml.sax.saxutils import escape

import requests
import xmltodict
from pharmacy_distributors.common.models import ScrapedProductInfo

from pharmacy_distributors.phoenix.phoenix import PhoenixPharma

# Create a logger for this module
logger = logging.getLogger(__name__)

# -*- coding: utf-8 -*-


class PhoenixPharmaOptimized(PhoenixPharma):
    REQUEST_TIMEOUT_SECONDS = 30

    def __init__(self, pharmacyID: str, shouldInitBrowser=True):
        super().__init__(pharmacyID, shouldInitBrowser)

        self.pharmacyID = pharmacyID
        self._partner_row: dict[str, Any] | None = None
        self._current_order_row: dict[str, Any] | None = None
        self._order_item_rows: list[dict[str, Any]] = []
        self._article_rows_by_name: dict[str, dict[str, Any]] = {}

    def prepare_for_order(self):
        self.remember_action("Preparing Phoenix order via API")
        self._ensure_order_initialized()

    def _get_php_session_id(self) -> str:
        php_session_id_cookie = self.browser.get_cookie("PHPSESSID")
        if php_session_id_cookie is None or not php_session_id_cookie.get("value"):
            raise RuntimeError("PhoenixPharma: PHPSESSID cookie is missing")
        return str(php_session_id_cookie["value"])

    def _request(
        self,
        method: str,
        path: str,
        *,
        query: str = "",
        data: str | bytes | None = None,
        content_type: str | None = None,
    ):
        headers = {"Cookie": f"PHPSESSID={self._get_php_session_id()}"}
        if content_type is not None:
            headers["Content-Type"] = content_type
        url = "https://b2b.phoenixpharma.bg/bg/build/production/BgShop/resources/php/" + path
        if query:
            url += "?" + query

        response = requests.request(
            method=method,
            url=url,
            headers=headers,
            data=data,
            timeout=self.REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        return response

    def _parse_xml_dataset(self, xml_text: str) -> dict[str, Any]:
        parsed = xmltodict.parse(xml_text)
        dataset = parsed.get("dataset")
        if not isinstance(dataset, dict):
            raise ValueError("PhoenixPharma: XML dataset response was not in the expected format")
        return dataset

    def _ensure_partner_loaded(self) -> dict[str, Any]:
        if self._partner_row is not None:
            return self._partner_row

        last_error: Exception | None = None
        for attempt in range(1, 4):
            self.remember_action(f"Loading Phoenix partner data for pharmacy {self.pharmacyID}")
            try:
                response = self._request(
                    "GET",
                    "combo/partner.php",
                    query=f"_dc=1&query={quote(self.pharmacyID)}&DaysDisableCashOnDelivery=11&page=1&start=0&limit=10",
                )
                dataset = self._parse_xml_dataset(response.text)
                partner_row = dataset.get("row")
                if isinstance(partner_row, dict):
                    self._partner_row = partner_row
                    return partner_row
                last_error = ValueError(f"Phoenix partner with pharmacy ID '{self.pharmacyID}' was not found.")
            except Exception as exc:
                last_error = exc

            logger.warning(
                "PhoenixPharma: Partner lookup attempt %s/3 failed for pharmacy %s: %s",
                attempt,
                self.pharmacyID,
                last_error,
            )
            time.sleep(1)

        raise last_error if last_error is not None else ValueError(
            f"Phoenix partner with pharmacy ID '{self.pharmacyID}' was not found."
        )

    def _ensure_order_initialized(self) -> dict[str, Any]:
        if self._current_order_row is not None:
            return self._current_order_row

        partner_row = self._ensure_partner_loaded()
        self.remember_action("Creating Phoenix order via API")

        assign_response = self._request("GET", "dataset/order/assignId.php", query="_dc=1")
        order_id = assign_response.json()["order_id"]

        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        order_payload = (
            "<dataset><row>"
            f"<order_id>{order_id}</order_id>"
            "<order_type>F</order_type>"
            "<order_state_id>100</order_state_id>"
            "<order_state_description>CREATED</order_state_description>"
            f"<order_created>{now}</order_created>"
            "<order_created_by>0</order_created_by>"
            "<order_created_by_realname></order_created_by_realname>"
            "<order_is_to>false</order_is_to>"
            "<order_confirm_user>0</order_confirm_user>"
            "<order_crmode>create</order_crmode>"
            "<order_ordered></order_ordered>"
            "<order_item_count>0</order_item_count>"
            "<TotalQuantity>0</TotalQuantity>"
            "<TotalBasePrice>0</TotalBasePrice>"
            "<TotalSalePrice>0</TotalSalePrice>"
            "<orderTourId></orderTourId>"
            "<orderTourDate></orderTourDate>"
            "<IsCashOrder>0</IsCashOrder>"
            "<order_ksc>0</order_ksc>"
            "<order_remark></order_remark>"
            f"<order_params>{{&quot;updateSumsLog&quot;:{{&quot;v&quot;:&quot;2&quot;,&quot;discountType&quot;:{partner_row['DiscountTypeIDFree']},&quot;algo&quot;:[]}}}}</order_params>"
            "<order_reference></order_reference>"
            f"<order_branch_number>{partner_row['BranchNo']}</order_branch_number>"
            f"<order_partner_number>{partner_row['IDF']}</order_partner_number>"
            f"<order_partner_name>{escape(self._xml_safe(partner_row.get('Name')))}</order_partner_name>"
            f"<order_partner_street>{escape(self._xml_safe(partner_row.get('Address')))}</order_partner_street>"
            f"<DiscountTypeIDFree>{partner_row['DiscountTypeIDFree']}</DiscountTypeIDFree>"
            f"<DiscountTypeIDNZOK>{partner_row['DiscountTypeIDNZOK']}</DiscountTypeIDNZOK>"
            "<order_created_by_email></order_created_by_email>"
            "<order_ordered_by_realname></order_ordered_by_realname>"
            "<order_ordered_by_email></order_ordered_by_email>"
            "<pharmosOrderNo>0</pharmosOrderNo>"
            "<xml_item_list>&lt;?xml version=&quot;1.0&quot; encoding=&quot;UTF-8&quot; standalone=&quot;yes&quot;?&gt;&lt;dataset&gt;&lt;/dataset&gt;</xml_item_list>"
            "<xml_package_list>&lt;?xml version=&quot;1.0&quot; encoding=&quot;UTF-8&quot; standalone=&quot;yes&quot;?&gt;&lt;dataset&gt;&lt;/dataset&gt;</xml_package_list>"
            "<AccNatRebateStart></AccNatRebateStart>"
            "<AccNatRebateEnd></AccNatRebateEnd>"
            "<AccNatRebateGroup>false</AccNatRebateGroup>"
            "<_htmlInvoice></_htmlInvoice>"
            "<sendResultSuccess>0</sendResultSuccess>"
            "<sendResultErrmsg></sendResultErrmsg>"
            "<deleted>0</deleted>"
            "<id>BgShop.model.order.OrderHeader-1</id>"
            f"<order_partner_id>{partner_row['partner_id']}</order_partner_id>"
            "</row></dataset>"
        )

        response = self._request(
            "POST",
            "dataset/order/commit.php",
            query="_dc=1",
            data=order_payload.encode("utf-8"),
            content_type="application/x-www-form-urlencoded; charset=UTF-8",
        )
        dataset = self._parse_xml_dataset(response.text)
        row = dataset.get("row")
        if not isinstance(row, dict):
            raise ValueError("PhoenixPharma: Order creation did not return the expected order row")

        self._current_order_row = row
        self._order_item_rows = self._decode_order_item_rows(row.get("xml_item_list"))
        return row

    def _get_json_result_of_search(self, product_name: str):
        partner_row = self._ensure_partner_loaded()
        response = self._request(
            "GET",
            "combo/article.php",
            query="selby=article"
            + "&query=" + quote(product_name)
            + "&order_type=F"
            + "&order_partner_id=" + quote(str(partner_row["partner_id"]))
            + "&mode=name_inside"
            + "&page=1&start=0",
        )
        return self._parse_xml_dataset(response.text)

    def _search_for_product_optimized(self, product_name: str) -> Tuple[Optional[dict[str, Any]], Optional[list[str]]]:
        self.remember_action(f"Searching Phoenix for product '{product_name}' via optimized endpoint")
        logger.info("PhoenixPharma._search_for_product_optimized(): Searching for product: '%s'...", product_name)
        dataset = self._get_json_result_of_search(product_name)
        if dataset is None:
            logger.error("PhoenixPharma._search_for_product_optimized(): Search result is empty...")
            return None, None

        number_of_results = int(dataset["results"])
        logger.info("PhoenixPharmaOptimized: number_of_results=%s", number_of_results)
        if number_of_results == 0:
            logger.error("PhoenixPharma._search_for_product_optimized(): Search result is empty...")
            return None, None

        rows = dataset.get("row", [])
        if isinstance(rows, dict):
            rows = [rows]

        filtered_rows = [row for row in rows if row.get("ExpiryDate") and row.get("isWebSaleProhibition") == "0"]
        if number_of_results > 1:
            self.lastSearchWasEmpty = False
            if len(filtered_rows) == 0:
                logger.error("PhoenixPharma: Found multiple products with search, but none of them have an expiry date, so we're skipping these products...")
                return None, None
            if len(filtered_rows) > 1:
                logger.error("PhoenixPharma: Found multiple products with search, but more than one of them have an expiry date, so we're skipping these products and we add the product names to the alternative names...")
                return None, [row["CyrName"] for row in filtered_rows]
            logger.info("PhoenixPharma: Found multiple products with search, but only one of them has an expiry date, so we're returning this product...")
            selected_row = filtered_rows[0]
        else:
            selected_row = rows[0]

        if not selected_row.get("ExpiryDate"):
            self.lastSearchWasEmpty = False
            logger.error("PhoenixPharma: Found product with search, but the expiry date was empty, so we're skipping this product...")
            return None, None

        if selected_row.get("isWebSaleProhibition") != "0":
            logger.error(
                "PhoenixPharma: Found product with search, but the product is not available for web sale, so we're skipping this product...: isWebSaleProhibition=%s",
                selected_row.get("isWebSaleProhibition"),
            )
            return None, None

        logger.info(
            "PhoenixPharma:_search_for_product_optimized(): Found product %s, with price: %s, and ExpiryDate: %s",
            selected_row.get("CyrName"),
            selected_row.get("pdPrice"),
            selected_row.get("ExpiryDate"),
        )
        self.lastSearchWasEmpty = False
        return selected_row, None

    def get_product_name_and_price(self, productSearchNames: list) -> ScrapedProductInfo:
        logger.info("PhoenixPharmaOptimized:get_product_name_and_price(): productSearchNames=%s", productSearchNames)
        all_alternative_names: set[str] = set()
        for productName in productSearchNames:
            article_row, alternative_names = self._search_for_product_optimized(productName)
            if alternative_names is not None:
                all_alternative_names.update(alternative_names)

            if article_row is None:
                continue

            result_product_name = article_row["CyrName"]
            self._article_rows_by_name[result_product_name] = article_row
            return ScrapedProductInfo(
                name=result_product_name,
                price=float(article_row["pdPrice"]) if article_row.get("pdPrice") is not None else math.inf,
                is_on_promotion=False,
                alternative_names=list(all_alternative_names),
            )

        return ScrapedProductInfo(
            name="",
            price=math.inf,
            is_on_promotion=False,
            alternative_names=list(all_alternative_names),
        )

    def _xml_safe(self, value: Any) -> str:
        return "" if value is None else str(value)

    def _build_order_item_row(self, article_row: dict[str, Any], quantity: int, item_index: int) -> dict[str, Any]:
        return {
            "order_item_id": "",
            "item_id": str(item_index),
            "article_id": self._xml_safe(article_row.get("article_id")),
            "article_number": self._xml_safe(article_row.get("article_number")),
            "CyrName": self._xml_safe(article_row.get("CyrName")),
            "LatName": self._xml_safe(article_row.get("LatName")),
            "ProducerName": self._xml_safe(article_row.get("ProducerName")),
            "BasePrice": self._xml_safe(article_row.get("BasePrice", "0")),
            "SalePrice": self._xml_safe(article_row.get("SalePrice", "0")),
            "CustomDiscPct": "0",
            "CustomDiscType": "A",
            "pdDisc": self._xml_safe(article_row.get("pdDisc", "0")),
            "pdPrice": self._xml_safe(article_row.get("pdPrice", "0")),
            "pdPharmacySellPrice": self._xml_safe(article_row.get("pdPharmacySellPrice", "0")),
            "order_id": "0",
            "quantity": str(quantity),
            "quantity_confirmed": "0",
            "RebateInKind": "0",
            "DiscPct": "0",
            "ExpiryDate": self._xml_safe(article_row.get("ExpiryDate")),
            "MeasureName": self._xml_safe(article_row.get("MeasureName")),
            "ProducerCode": self._xml_safe(article_row.get("ProducerCode")),
            "MaxPrice": self._xml_safe(article_row.get("MaxPrice", "0")),
            "NHIFCode": self._xml_safe(article_row.get("NHIFCode")),
            "NHIFSalePrice": self._xml_safe(article_row.get("NHIFSalePrice", "0")),
            "NHIFBasePrice": self._xml_safe(article_row.get("NHIFBasePrice", "0")),
            "NHIFMaxPrice": self._xml_safe(article_row.get("NHIFMaxPrice", "0")),
            "isMedicalPrescription": self._xml_safe(article_row.get("isMedicalPrescription", "0")),
            "isWebSaleProhibition": self._xml_safe(article_row.get("isWebSaleProhibition", "0")),
            "isDrugstoreAllowed": self._xml_safe(article_row.get("isDrugstoreAllowed", "0")),
            "isDrug": self._xml_safe(article_row.get("isDrug", "0")),
            "isForRefrigerator": self._xml_safe(article_row.get("isForRefrigerator", "0")),
            "AdvertismentText": self._xml_safe(article_row.get("AdvertismentText")),
            "Barcode1": self._xml_safe(article_row.get("Barcode1")),
            "Barcode2": self._xml_safe(article_row.get("Barcode2")),
            "Description": self._xml_safe(article_row.get("Description")),
            "lastupdate": self._xml_safe(article_row.get("lastupdate")),
            "StockLevel": self._xml_safe(article_row.get("StockLevel", "0")),
            "promo_count": "0",
            "json_promo_list": self._xml_safe(article_row.get("json_promo_list", "[]")),
            "deleted": "0",
            "id": f"BgShop.model.order.OrderItem-{item_index}",
        }

    def _encode_order_items_xml(self, items: list[dict[str, Any]]) -> str:
        row_xml_parts: list[str] = []
        for item in items:
            row_xml_parts.append(
                "<row>"
                f"<order_item_id>{escape(self._xml_safe(item.get('order_item_id')))}</order_item_id>"
                f"<item_id>{escape(self._xml_safe(item.get('item_id')))}</item_id>"
                f"<article_id>{escape(self._xml_safe(item.get('article_id')))}</article_id>"
                f"<article_number>{escape(self._xml_safe(item.get('article_number')))}</article_number>"
                f"<CyrName>{escape(self._xml_safe(item.get('CyrName')))}</CyrName>"
                f"<LatName>{escape(self._xml_safe(item.get('LatName')))}</LatName>"
                f"<ProducerName>{escape(self._xml_safe(item.get('ProducerName')))}</ProducerName>"
                f"<BasePrice>{escape(self._xml_safe(item.get('BasePrice')))}</BasePrice>"
                f"<SalePrice>{escape(self._xml_safe(item.get('SalePrice')))}</SalePrice>"
                f"<CustomDiscPct>{escape(self._xml_safe(item.get('CustomDiscPct')))}</CustomDiscPct>"
                f"<CustomDiscType>{escape(self._xml_safe(item.get('CustomDiscType')))}</CustomDiscType>"
                f"<pdDisc>{escape(self._xml_safe(item.get('pdDisc')))}</pdDisc>"
                f"<pdPrice>{escape(self._xml_safe(item.get('pdPrice')))}</pdPrice>"
                f"<pdPharmacySellPrice>{escape(self._xml_safe(item.get('pdPharmacySellPrice')))}</pdPharmacySellPrice>"
                f"<order_id>{escape(self._xml_safe(item.get('order_id')))}</order_id>"
                f"<quantity>{escape(self._xml_safe(item.get('quantity')))}</quantity>"
                f"<quantity_confirmed>{escape(self._xml_safe(item.get('quantity_confirmed')))}</quantity_confirmed>"
                f"<RebateInKind>{escape(self._xml_safe(item.get('RebateInKind')))}</RebateInKind>"
                f"<DiscPct>{escape(self._xml_safe(item.get('DiscPct')))}</DiscPct>"
                f"<ExpiryDate>{escape(self._xml_safe(item.get('ExpiryDate')))}</ExpiryDate>"
                f"<MeasureName>{escape(self._xml_safe(item.get('MeasureName')))}</MeasureName>"
                f"<ProducerCode>{escape(self._xml_safe(item.get('ProducerCode')))}</ProducerCode>"
                f"<MaxPrice>{escape(self._xml_safe(item.get('MaxPrice')))}</MaxPrice>"
                f"<NHIFCode>{escape(self._xml_safe(item.get('NHIFCode')))}</NHIFCode>"
                f"<NHIFSalePrice>{escape(self._xml_safe(item.get('NHIFSalePrice')))}</NHIFSalePrice>"
                f"<NHIFBasePrice>{escape(self._xml_safe(item.get('NHIFBasePrice')))}</NHIFBasePrice>"
                f"<NHIFMaxPrice>{escape(self._xml_safe(item.get('NHIFMaxPrice')))}</NHIFMaxPrice>"
                f"<isMedicalPrescription>{escape(self._xml_safe(item.get('isMedicalPrescription')))}</isMedicalPrescription>"
                f"<isWebSaleProhibition>{escape(self._xml_safe(item.get('isWebSaleProhibition')))}</isWebSaleProhibition>"
                f"<isDrugstoreAllowed>{escape(self._xml_safe(item.get('isDrugstoreAllowed')))}</isDrugstoreAllowed>"
                f"<isDrug>{escape(self._xml_safe(item.get('isDrug')))}</isDrug>"
                f"<isForRefrigerator>{escape(self._xml_safe(item.get('isForRefrigerator')))}</isForRefrigerator>"
                f"<AdvertismentText>{escape(self._xml_safe(item.get('AdvertismentText')))}</AdvertismentText>"
                f"<Barcode1>{escape(self._xml_safe(item.get('Barcode1')))}</Barcode1>"
                f"<Barcode2>{escape(self._xml_safe(item.get('Barcode2')))}</Barcode2>"
                f"<Description>{escape(self._xml_safe(item.get('Description')))}</Description>"
                f"<lastupdate>{escape(self._xml_safe(item.get('lastupdate')))}</lastupdate>"
                f"<StockLevel>{escape(self._xml_safe(item.get('StockLevel')))}</StockLevel>"
                f"<promo_count>{escape(self._xml_safe(item.get('promo_count')))}</promo_count>"
                f"<json_promo_list>{escape(self._xml_safe(item.get('json_promo_list')))}</json_promo_list>"
                f"<deleted>{escape(self._xml_safe(item.get('deleted')))}</deleted>"
                f"<id>{escape(self._xml_safe(item.get('id')))}</id>"
                "</row>"
            )

        item_xml = "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?><dataset>" + "".join(row_xml_parts) + "</dataset>"
        return escape(item_xml).replace("\"", "&quot;")

    def _decode_order_item_rows(self, xml_item_list: Any) -> list[dict[str, Any]]:
        xml_item_list_text = self._xml_safe(xml_item_list).strip()
        if xml_item_list_text == "":
            return []

        decoded_xml = html.unescape(xml_item_list_text)
        try:
            dataset = self._parse_xml_dataset(decoded_xml)
        except Exception:
            return []

        rows = dataset.get("row")
        if rows is None:
            return []
        if isinstance(rows, list):
            return [row for row in rows if isinstance(row, dict)]
        if isinstance(rows, dict):
            return [rows]
        return []

    def _build_commit_payload(self, order_row: dict[str, Any], items: list[dict[str, Any]]) -> bytes:
        total_quantity = sum(int(self._xml_safe(item.get("quantity", "0")) or "0") for item in items)
        total_base_price = sum(float(self._xml_safe(item.get("BasePrice", "0")) or "0") * int(self._xml_safe(item.get("quantity", "0")) or "0") for item in items)
        total_sale_price = sum(float(self._xml_safe(item.get("SalePrice", "0")) or "0") * int(self._xml_safe(item.get("quantity", "0")) or "0") for item in items)

        algo_parts = []
        for index, item in enumerate(items, start=1):
            quantity = int(self._xml_safe(item.get("quantity", "0")) or "0")
            algo_parts.append(
                "{&quot;i&quot;:"
                + str(index)
                + ",&quot;q&quot;:"
                + str(quantity)
                + ",&quot;p1&quot;:"
                + self._xml_safe(item.get("SalePrice", "0"))
                + ",&quot;p2&quot;:"
                + self._xml_safe(item.get("pdPrice", "0"))
                + "}"
            )

        payload = (
            "<dataset><row>"
            f"<order_id>{self._xml_safe(order_row.get('order_id'))}</order_id>"
            f"<order_type>{self._xml_safe(order_row.get('order_type', 'F'))}</order_type>"
            f"<order_state_id>{self._xml_safe(order_row.get('order_state_id', '100'))}</order_state_id>"
            f"<order_partner_id>{self._xml_safe(order_row.get('order_partner_id'))}</order_partner_id>"
            f"<order_is_to>{self._xml_safe(order_row.get('order_is_to', '0'))}</order_is_to>"
            f"<order_created>{escape(self._xml_safe(order_row.get('order_created')))}</order_created>"
            f"<order_created_by>{self._xml_safe(order_row.get('order_created_by', '0'))}</order_created_by>"
            f"<order_ordered>{escape(self._xml_safe(order_row.get('order_ordered')))}</order_ordered>"
            f"<order_confirm_user>{self._xml_safe(order_row.get('order_confirm_user', '0'))}</order_confirm_user>"
            f"<order_ksc>{self._xml_safe(order_row.get('order_ksc', '0'))}</order_ksc>"
            f"<order_remark>{escape(self._xml_safe(order_row.get('order_remark')))}</order_remark>"
            f"<order_params>{{&quot;updateSumsLog&quot;:{{&quot;v&quot;:&quot;2&quot;,&quot;discountType&quot;:{self._xml_safe(order_row.get('DiscountTypeIDFree', '0'))},&quot;algo&quot;:[{','.join(algo_parts)}]}}}}</order_params>"
            f"<order_reference>{escape(self._xml_safe(order_row.get('order_reference')))}</order_reference>"
            f"<order_crmode>{self._xml_safe(order_row.get('order_crmode', 'create'))}</order_crmode>"
            f"<deleted>{self._xml_safe(order_row.get('deleted', '0'))}</deleted>"
            f"<order_item_count>{len(items)}</order_item_count>"
            f"<TotalQuantity>{total_quantity}</TotalQuantity>"
            f"<TotalBasePrice>{total_base_price:.2f}</TotalBasePrice>"
            f"<TotalSalePrice>{total_sale_price:.2f}</TotalSalePrice>"
            f"<order_state_description>{escape(self._xml_safe(order_row.get('order_state_description', 'CREATED')))}</order_state_description>"
            f"<order_branch_number>{self._xml_safe(order_row.get('order_branch_number'))}</order_branch_number>"
            f"<order_partner_number>{self._xml_safe(order_row.get('order_partner_number'))}</order_partner_number>"
            f"<order_partner_licence>{escape(self._xml_safe(order_row.get('order_partner_licence')))}</order_partner_licence>"
            f"<order_partner_name>{escape(self._xml_safe(order_row.get('order_partner_name')))}</order_partner_name>"
            f"<order_partner_street>{escape(self._xml_safe(order_row.get('order_partner_street')))}</order_partner_street>"
            f"<DiscountTypeIDFree>{self._xml_safe(order_row.get('DiscountTypeIDFree', '0'))}</DiscountTypeIDFree>"
            f"<DiscountTypeIDNZOK>{self._xml_safe(order_row.get('DiscountTypeIDNZOK', '0'))}</DiscountTypeIDNZOK>"
            f"<order_partner_phone>{escape(self._xml_safe(order_row.get('order_partner_phone')))}</order_partner_phone>"
            f"<order_created_by_realname>{escape(self._xml_safe(order_row.get('order_created_by_realname')))}</order_created_by_realname>"
            f"<order_created_by_email>{escape(self._xml_safe(order_row.get('order_created_by_email')))}</order_created_by_email>"
            f"<order_created_by_mail_on_qty_change>{self._xml_safe(order_row.get('order_created_by_mail_on_qty_change', '1'))}</order_created_by_mail_on_qty_change>"
            f"<order_ordered_by_realname>{escape(self._xml_safe(order_row.get('order_ordered_by_realname')))}</order_ordered_by_realname>"
            f"<order_ordered_by_email>{escape(self._xml_safe(order_row.get('order_ordered_by_email')))}</order_ordered_by_email>"
            f"<order_ordered_by_phone>{escape(self._xml_safe(order_row.get('order_ordered_by_phone')))}</order_ordered_by_phone>"
            f"<pharmosOrderNo>{self._xml_safe(order_row.get('pharmosOrderNo', '0'))}</pharmosOrderNo>"
            f"<boehringer>{self._xml_safe(order_row.get('boehringer', '0'))}</boehringer>"
            f"<sendResultErrmsg>{escape(self._xml_safe(order_row.get('sendResultErrmsg', '_')))}</sendResultErrmsg>"
            f"<xml_item_list>{self._encode_order_items_xml(items)}</xml_item_list>"
            f"<xml_package_list>{escape(self._xml_safe(order_row.get('xml_package_list')))}</xml_package_list>"
            f"<whole_protocol_xml>{escape(self._xml_safe(order_row.get('whole_protocol_xml')))}</whole_protocol_xml>"
            f"<orderTourId>{escape(self._xml_safe(order_row.get('orderTourId')))}</orderTourId>"
            f"<orderTourDate>{escape(self._xml_safe(order_row.get('orderTourDate')))}</orderTourDate>"
            f"<AccNatRebateStart>{escape(self._xml_safe(order_row.get('AccNatRebateStart')))}</AccNatRebateStart>"
            f"<AccNatRebateEnd>{escape(self._xml_safe(order_row.get('AccNatRebateEnd')))}</AccNatRebateEnd>"
            f"<AccNatRebateGroup>{self._xml_safe(order_row.get('AccNatRebateGroup', '0'))}</AccNatRebateGroup>"
            f"<order_comment>{escape(self._xml_safe(order_row.get('order_comment')))}</order_comment>"
            f"<LastStatusCheck>{escape(self._xml_safe(order_row.get('LastStatusCheck')))}</LastStatusCheck>"
            f"<order_ordered_by>{escape(self._xml_safe(order_row.get('order_ordered_by')))}</order_ordered_by>"
            f"<tr_order_item_count>{self._xml_safe(order_row.get('tr_order_item_count', '0'))}</tr_order_item_count>"
            f"<tr_TotalQuantity>{escape(self._xml_safe(order_row.get('tr_TotalQuantity')))}</tr_TotalQuantity>"
            f"<tr_TotalBasePrice>{self._xml_safe(order_row.get('tr_TotalBasePrice', '0.00'))}</tr_TotalBasePrice>"
            f"<tr_TotalSalePrice>{self._xml_safe(order_row.get('tr_TotalSalePrice', '0.00'))}</tr_TotalSalePrice>"
            f"<FullOrderValue>{escape(self._xml_safe(order_row.get('FullOrderValue')))}</FullOrderValue>"
            f"<id>BgShop.model.order.OrderHeader-{max(len(items), 1) + 2}</id>"
            "</row></dataset>"
        )
        return payload.encode("utf-8")

    def _commit_order_items(self, items: list[dict[str, Any]]):
        if self._current_order_row is None:
            raise RuntimeError("PhoenixPharma: Order state is not initialized before item commit")

        response = self._request(
            "POST",
            "dataset/order/commit.php",
            query=f"_dc={int(datetime.now().timestamp() * 1000)}",
            data=self._build_commit_payload(self._current_order_row, items),
            content_type="application/x-www-form-urlencoded; charset=UTF-8",
        )
        dataset = self._parse_xml_dataset(response.text)
        row = dataset.get("row")
        if not isinstance(row, dict):
            raise ValueError("PhoenixPharma: Item commit did not return the expected order row")

        self._current_order_row = row
        self._order_item_rows = self._decode_order_item_rows(row.get("xml_item_list"))

    def add_product_to_cart(self, product_name: str, quantity):
        self.remember_action(f"Adding product '{product_name}' to Phoenix cart with quantity {quantity} via API")
        logger.info("PhoenixPharmaOptimized: Adding product to cart via API: %s, quantity: %s", product_name, quantity)

        self._ensure_order_initialized()
        article_row = self._article_rows_by_name.get(product_name)
        if article_row is None:
            article_row, _ = self._search_for_product_optimized(product_name)
        if article_row is None:
            logger.error("PhoenixPharma: Could not load product details for direct API cart insertion: %s", product_name)
            return None

        new_item = self._build_order_item_row(article_row, quantity, len(self._order_item_rows) + 1)
        items = list(self._order_item_rows) + [new_item]
        try:
            self._commit_order_items(items)
            return True
        except Exception as exc:
            logger.error("PhoenixPharma: Direct API add-to-cart failed, falling back to UI flow: %s", exc)
            try:
                self.refresh_page()
                self._search_for_product(product_name)
                self._add_product_to_cart_optimized(quantity)
                return True
            except Exception as fallback_exc:
                logger.error("PhoenixPharma: Fallback UI add-to-cart failed: %s", fallback_exc)
                raise
