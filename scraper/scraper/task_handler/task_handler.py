import json
import logging
import math
import os
from typing import List, Optional

from dal.cosmosdb_client import CosmosDbClient
from pharmacy_distributors.common.models import ScrapedProductInfo
from selenium.common.exceptions import StaleElementReferenceException
from messaging.messaging import ScraperTaskItem
from pharmacy_distributors.common.browser_common import BrowserCommon
from pharmacy_distributors.sting.sting import StingPharma
from pharmacy_distributors.phoenix.phoenix_optimized import PhoenixPharmaOptimized
from files.file_worker import FileWorker, RowInfo
from files.file_worker_factory import FileWorkerFactory
from files.azure_blob_client import AzureBlobClient
from task_handler.task_update_publisher import TaskUpdatePublisher
from psa_logger.logger import get_current_logfile_name, get_current_logfile_data
import concurrent.futures

# Create a logger for this module
logger = logging.getLogger(__name__)


def _short_error_reason(error_message: str) -> str:
    lowered = error_message.lower()
    if "pharmacy id not found" in lowered:
        return "няма конфигурация за избраната аптека"
    if "element click intercepted" in lowered:
        return "елементът не може да бъде кликнат, защото друг елемент го покрива"
    if "not found or could not be selected" in lowered:
        return "неуспешен избор на клиент"
    if "couldn't open input file" in lowered or "input file is not opened" in lowered:
        return "входният файл не може да бъде отворен"
    if "json content is not valid" in lowered:
        return "JSON съдържанието не е валидно"
    if "json content is not loaded" in lowered:
        return "JSON съдържанието не е заредено"
    if "all rows must be dictionaries" in lowered:
        return "входните редове са в невалиден формат"
    if "database is not initialized" in lowered:
        return "връзката с базата данни не е инициализирана"
    if "php sessid cookie is missing" in lowered:
        return "липсва активна Phoenix сесия"
    if "price header position was not found" in lowered:
        return "не е открита колоната с цена"
    if "target table row with an expiry date" in lowered:
        return "не е открит ред с валиден срок на годност"
    if "aborted by navigation" in lowered:
        return "страницата се презареди или навигацията беше прекъсната"
    if "timeout" in lowered:
        return "операцията изтече по време"
    if "проблем с входния excel файл" in lowered:
        return "входният Excel файл е невалиден"
    return error_message.strip() if error_message.strip() != "" else error_message.__class__.__name__


def _find_matching_scraper(error_message: str, scrapers: List[BrowserCommon]) -> BrowserCommon | None:
    matching_scraper = next((scraper for scraper in scrapers if scraper.get_name().lower() in error_message.lower()), None)
    if matching_scraper is None and scrapers:
        matching_scraper = scrapers[-1]
    return matching_scraper


def build_task_error_summary(
    error: Exception,
    scrapers: List[BrowserCommon],
    *,
    stage: str | None = None,
    operation: str | None = None,
) -> str:
    error_message = str(error)
    matching_scraper = _find_matching_scraper(error_message, scrapers)
    reason = _short_error_reason(error_message)
    if stage is None:
        stage = "Изпълнение на задачата"

    if operation is None:
        if matching_scraper is not None and getattr(matching_scraper, "current_action", None):
            operation = matching_scraper.current_action
        else:
            operation = "неизвестна операция"

    if matching_scraper is None:
        return f"{stage}: стъпка '{operation}' се провали, защото {reason}."

    return f"{matching_scraper.get_name()} - {stage}: стъпка '{operation}' се провали, защото {reason}."


def build_task_error_details(error: Exception, scrapers: List[BrowserCommon]) -> str:
    details = [f"Message: {str(error) if str(error).strip() != '' else repr(error)}"]
    for scraper in scrapers:
        details.append("")
        details.append(scraper.format_debug_context())
    return "\n".join(details)


def build_task_progress_message(original_product_name: str | None, current_input_row: int, total_number_of_rows: int) -> str:
    if original_product_name:
        return (
            f"Обработва се продукт '{original_product_name}' "
            f"({current_input_row} от {total_number_of_rows})"
        )
    return f"Обработва се ред {current_input_row} от {total_number_of_rows}"


class ProductInfo:
    def __init__(self, scraper: BrowserCommon, name: str, price: Optional[float], is_on_promotion: bool, alternative_names: List[str]):
        self.scraper = scraper
        self.name = name
        self.price = price
        self.is_on_promotion = is_on_promotion
        self.alternative_names = alternative_names if alternative_names is not None else []

        if self.scraper is None:
            raise ValueError("Scraper must not be None")
        if not isinstance(name, str):
            raise ValueError("Product name must be a string")
        if not isinstance(price, float) and price is not None:
            raise ValueError("Product price must be a float or None")
        if not isinstance(is_on_promotion, bool):
            raise ValueError("Is on promotion must be a boolean")
        if not isinstance(alternative_names, List) and alternative_names is not None:
            raise ValueError("Alternative names must be a list or None")

    def get_price(self) -> float:
        return self.price if self.price is not None else math.inf

    # string representation of the object
    def __str__(self):
        return f"ProductInfo(scraper={self.scraper}, name={self.name}, price={self.price}, is_on_promotion={self.is_on_promotion}, alternative_names={self.alternative_names})"

    def __dict__(self):
        return {
            "distributor": self.scraper.name,
            "name": self.name,
            "price": self.price,
            "is_on_promotion": self.is_on_promotion,
            "alternative_names": self.alternative_names
        }


class BoughtProductInfo:
    def __init__(self, original_product_name: str, all_pharmacy_product_infos: List[ProductInfo], bought_from_distributor: str):
        self.original_product_name = original_product_name
        self.all_pharmacy_product_infos = all_pharmacy_product_infos
        self.bought_from_distributor = bought_from_distributor

        if not isinstance(original_product_name, str):
            raise ValueError("Original product name must be a string")
        if not isinstance(all_pharmacy_product_infos, List):
            raise ValueError("All pharmacy product infos must be a list")
        if not all(isinstance(product_info, ProductInfo) for product_info in all_pharmacy_product_infos):
            raise ValueError(
                "All pharmacy product infos must be a list of ProductInfo")
        if not isinstance(bought_from_distributor, str):
            raise ValueError("Bought from pharmacy must be a string")

    def __dict__(self):
        return {
            "original_product_name": self.original_product_name,
            "all_pharmacy_product_infos": [product_info.__dict__() for product_info in self.all_pharmacy_product_infos],
            "bought_from_distributor": self.bought_from_distributor
        }


class UnboughtProductInfo:
    def __init__(self, product_name: str, quantity: int, alternative_names: List[str]):
        self.product_name = product_name
        self.quantity = quantity
        self.alternative_names = alternative_names

        if not isinstance(product_name, str):
            raise ValueError("Product name must be a string")
        if not isinstance(quantity, int):
            raise ValueError("Quantity must be an integer")

    def __dict__(self):
        return {
            "product_name": self.product_name,
            "quantity": self.quantity,
            "alternative_names": self.alternative_names
        }


class TaskReport:
    def __init__(self, bought_products: List[BoughtProductInfo], unbought_products: List[UnboughtProductInfo]):
        self.bought_products = bought_products
        self.unbought_products = unbought_products

    def __dict__(self):
        return {
            "bought_products": [bought_product.__dict__() for bought_product in self.bought_products],
            "unbought_products": [unbought_product.__dict__() for unbought_product in self.unbought_products]
        }


class TaskHandler:
    def __init__(self, taskItem: ScraperTaskItem):
        self.taskItem = taskItem
        self.task_update_publisher: TaskUpdatePublisher | None = None
        self.scrapers: List[BrowserCommon] = []
        self.bought_products: List[BoughtProductInfo] = []
        self.unbought_products: List[UnboughtProductInfo] = []
        self.cosmos_db_client: CosmosDbClient | None = None
        self._custom_variations_by_product_name: dict[str, list[str]] = {}
        self._variation_doc_id_by_product_name: dict[str, str] = {}
        self._pending_generated_variations_by_product_name: dict[str, list[str]] = {}
        try:
            self.file_worker: FileWorker = FileWorkerFactory(
                taskItem.file_type).get_file_worker()
            self.task_update_publisher = TaskUpdatePublisher()
            self.scrapers = self._get_scrapers()
        except Exception as e:
            logger.exception("TaskHandler: Couldn't initialize the task handler: %s", e)
            if self.task_update_publisher is not None:
                self.task_update_publisher.publish_error(
                    taskItem=self.taskItem,
                    message="Couldn't initialize the task handler",
                    detailed_error_message=str(e),
                    progress=0)
            raise

    def handle_task(self):
        logger.info(f"Handling task: {self.taskItem.to_json()}")
        try:
            self._open_and_validate_input_file()
            self._prepare_custom_product_name_variations_cache()
            for scraper in self.scrapers:
                scraper.login()
                scraper.prepare_for_order()

            self._work_loop()

            self.task_update_publisher.publish_success(self.taskItem, self._generate_report().__dict__())
        except Exception as e:
            logger.exception(f"TaskHandler: Failed to handle the task: {str(e)}")
            blob_client = AzureBlobClient()
            try:
                blob_client.upload_blob_to_log_container(get_current_logfile_name(), get_current_logfile_data())
            except Exception as e_logfile:
                logger.error(f"TaskHandler: Couldn't upload the log file: {e_logfile}")

            image_urls = []
            for scraper in self.scrapers:
                scraper_temporary_screenshots = scraper.get_temporary_screenshots()
                for screenshotPng, screenshotName in scraper_temporary_screenshots:
                    image_urls.append(
                        f"https://psaonlinestorage.blob.core.windows.net/{os.getenv('AZURE_BLOB_STORAGE_OUTPUT_FILES_CONTAINER_NAME')}/{screenshotName}")
                    blob_client.upload_blob_to_output_container(screenshotName, screenshotPng[:])
                screenshotPng, screenshotName = scraper.getScreenshot()
                image_urls.append(
                    f"https://psaonlinestorage.blob.core.windows.net/{os.getenv('AZURE_BLOB_STORAGE_OUTPUT_FILES_CONTAINER_NAME')}/{screenshotName}")
                blob_client.upload_blob_to_output_container(screenshotName, screenshotPng[:])

            self.task_update_publisher.publish_error(
                taskItem=self.taskItem,
                message=build_task_error_summary(e, self.scrapers),
                detailed_error_message=build_task_error_details(e, self.scrapers),
                progress=0,
                image_urls=image_urls)
            return
        finally:
            try:
                self._flush_custom_product_name_variations_cache()
            except Exception as flush_error:
                logger.error("TaskHandler: Couldn't flush product name variations cache: %s", flush_error)

    def _get_scrapers(self) -> List[BrowserCommon]:
        scrapers: List[BrowserCommon] = []

        for distributor in self.taskItem.distributors:
            if distributor == "sting":
                logger.info("TaskHandler: Handling task for Sting")
                scrapers.append(StingPharma(self.taskItem.pharmacy_id))
            elif distributor == "phoenix":
                logger.info("TaskHandler: Handling task for Phoenix")
                scrapers.append(PhoenixPharmaOptimized(
                    self.taskItem.pharmacy_id))

        return scrapers

    def _open_and_validate_input_file(self):
        try:
            self.file_worker.open_file(self.taskItem.file_data)
        except Exception as e:
            logger.error("TaskHandler: Couldn't open the file: ", e)
            self.task_update_publisher.publish_error(
                taskItem=self.taskItem,
                message=build_task_error_summary(
                    e,
                    self.scrapers,
                    stage="Зареждане на входния файл",
                    operation=self.taskItem.file_name,
                ),
                detailed_error_message=build_task_error_details(e, self.scrapers),
                progress=0)
            raise e

        try:
            self.file_worker.validate_input()
        except Exception as e:
            logger.error("TaskHandler: Couldn't validate the input file: ", e)
            self.task_update_publisher.publish_error(
                taskItem=self.taskItem,
                message=build_task_error_summary(
                    e,
                    self.scrapers,
                    stage="Валидиране на входния файл",
                    operation=self.taskItem.file_name,
                ),
                detailed_error_message=build_task_error_details(e, self.scrapers),
                progress=0)
            raise e

    def _work_loop(self):
        progress_percent = 0
        while True:
            try:
                row_info: RowInfo = self.file_worker.get_next_row()
            except Exception as e:
                logger.error("TaskHandler: Couldn't get next row: ", e)
                self.task_update_publisher.publish_error(
                    taskItem=self.taskItem,
                    message=build_task_error_summary(
                        e,
                        self.scrapers,
                        stage="Обработка на входните данни",
                        operation="прочитане на следващ ред",
                    ),
                    detailed_error_message=build_task_error_details(e, self.scrapers),
                    progress=progress_percent)
                raise e
            if row_info.product_name_variations is None or row_info.product_quantity is None:
                logger.info(
                    f"TaskHandler: No more rows to process: {row_info}")
                break
            try:
                self._get_custom_product_name_variations(row_info)
            except Exception as e:
                logger.error(
                    "TaskHandler: Couldn't get custom product name variations: ", e)
                self.task_update_publisher.publish_error(
                    taskItem=self.taskItem,
                    message=build_task_error_summary(
                        e,
                        self.scrapers,
                        stage="Подготовка на търсенето",
                        operation=f"извличане на вариации за '{row_info.original_product_name}'",
                    ),
                    detailed_error_message=build_task_error_details(e, self.scrapers),
                    progress=progress_percent)
                raise e

            progress = self.file_worker.get_progress()
            progress_percent = math.floor(
                progress.current_input_row / progress.total_number_of_rows * 100)
            self.task_update_publisher.publish_progress_update(
                taskItem=self.taskItem,
                message=build_task_progress_message(
                    progress.original_product_name,
                    progress.current_input_row,
                    progress.total_number_of_rows,
                ),
                progress=progress_percent)

            self.buy_lowest_price_for_product(
                productName=progress.original_product_name,
                productSearchNames=row_info.custom_product_name_variations + row_info.product_name_variations,
                quantity=row_info.product_quantity)

    def buy_lowest_price_for_product(self, productName: str, productSearchNames: List[str], quantity: int):
        logger.info(f"Getting prices for: {productName}")
        all_product_prices: List[ProductInfo] = self._get_all_prices(productSearchNames)
        best_product: ProductInfo | None = None
        for product in all_product_prices:
            logger.info(f"Product ({product.scraper.get_name()}): {product.name}, Price: {product.price}, Alternative names: {product.alternative_names}")
            if best_product is None or product.get_price() < best_product.get_price():
                best_product = product
            elif product.price == best_product.price:
                if product.scraper.get_priority() < best_product.scraper.get_priority():
                    best_product = product

        if best_product is None or best_product.price == math.inf:
            logger.error(f"Couldn't find product: {productName}")
            alternative_names = [name for product in all_product_prices for name in product.alternative_names]
            self._store_unbought_product(productName, quantity, alternative_names)
            return

        logger.info(
            f"Best product: {best_product.name}, Price: {best_product.price}, added To {best_product.scraper.get_name()}")
        try:
            # Critical ordering invariant:
            # it is safer to leave a row unbought than to buy the wrong product or
            # accidentally increase the quantity of another product because of a bad match.
            if best_product.scraper.add_product_to_cart(best_product.name, quantity):
                self._store_bought_product(
                    productName, all_product_prices, best_product.scraper.get_name())
            else:
                logger.error(
                    f"Product found, but couldn't be added to cart: {productName}")
                self._store_unbought_product(productName, quantity, alternative_names=[])
        except Exception as e:
            raise Exception(f"{best_product.scraper.get_name()}: {str(e)}")

    def _get_all_prices(self, productSearchNames: List[str]) -> List[ProductInfo]:
        logger.info(
            f"TaskHandler: Getting all prices for: {productSearchNames}")
        result: List[ProductInfo] = []

        def get_product_info(scraper: BrowserCommon, productSearchNames: List[str]) -> ProductInfo | None:
            try:
                scraped_product_info: ScrapedProductInfo = scraper.get_product_name_and_price(productSearchNames)
            except StaleElementReferenceException:
                # retry
                scraper.refresh_page()
                try:
                    scraped_product_info: ScrapedProductInfo = scraper.get_product_name_and_price(productSearchNames)
                except Exception as e:
                    logger.error("TaskHandler: Couldn't get product name and price: ", e)
                    return None
            if scraped_product_info.price != math.inf or len(scraped_product_info.alternative_names) > 0:
                return ProductInfo(
                    scraper,
                    scraped_product_info.name,
                    scraped_product_info.price,
                    scraped_product_info.is_on_promotion,
                    alternative_names=scraped_product_info.alternative_names)
            return None

        with concurrent.futures.ThreadPoolExecutor() as executor:
            future_to_scraper = {executor.submit(get_product_info, scraper, productSearchNames): scraper for scraper in self.scrapers}
            for future in concurrent.futures.as_completed(future_to_scraper):
                try:
                    product_info = future.result()
                    if product_info is not None:
                        result.append(product_info)
                except Exception as e:
                    logger.error(
                        f"TaskHandler: Couldn't get product info with futures: {str(e)}")

        logger.info(
            f"TaskHandler: All prices: {[(info.scraper.get_name(), info.name, info.price, info.alternative_names) for info in result]}")
        return result

    def _store_bought_product(self, original_product_name: str, all_pharmacy_product_infos: List[ProductInfo], bought_from_distributor: str):
        bought_product = BoughtProductInfo(
            original_product_name, all_pharmacy_product_infos, bought_from_distributor)
        self.bought_products.append(bought_product)

    def _store_unbought_product(self, product_name: str, quantity: int, alternative_names: List[str]):
        unbought_product = UnboughtProductInfo(product_name, quantity, alternative_names)
        self.unbought_products.append(unbought_product)

    def _generate_report(self) -> TaskReport:
        """
        Generates JSON report for the task
        """
        report = TaskReport([], [])

        for bought_product in self.bought_products:
            bought_product_dict = BoughtProductInfo(
                original_product_name=bought_product.original_product_name,
                all_pharmacy_product_infos=[
                    ProductInfo(
                        scraper=product_info.scraper,
                        name=product_info.name,
                        price=product_info.price if product_info.price != math.inf else None,
                        is_on_promotion=product_info.is_on_promotion,
                        alternative_names=product_info.alternative_names
                    ) for product_info in bought_product.all_pharmacy_product_infos
                ],
                bought_from_distributor=bought_product.bought_from_distributor
            )
            report.bought_products.append(bought_product_dict)

        for unbought_product in self.unbought_products:
            unbought_product_dict = UnboughtProductInfo(
                product_name=unbought_product.product_name,
                quantity=unbought_product.quantity,
                alternative_names=unbought_product.alternative_names
            )
            report.unbought_products.append(unbought_product_dict)

        return report

    def _get_custom_product_name_variations(self, row_info: RowInfo):
        """
        Fetches custom product name variations from the CosmosDB database
        """
        if row_info.original_product_name is None:
            row_info.custom_product_name_variations = []
            return

        row_info.custom_product_name_variations = self._custom_variations_by_product_name.get(
            row_info.original_product_name,
            [],
        )
        self._pending_generated_variations_by_product_name[row_info.original_product_name] = row_info.product_name_variations

    def _prepare_custom_product_name_variations_cache(self):
        original_product_names = self.file_worker.get_distinct_original_product_names()
        if not original_product_names:
            return

        self.cosmos_db_client = CosmosDbClient()
        items = self.cosmos_db_client.read_items(
            collection_name="product_name_variations",
            filter={"original_product_name": {"$in": original_product_names}},
            projection={"custom_product_name_variations": 1, "original_product_name": 1},
        )

        self._custom_variations_by_product_name = {
            item["original_product_name"]: item.get("custom_product_name_variations", [])
            for item in items
            if item.get("original_product_name") is not None
        }
        self._variation_doc_id_by_product_name = {
            item["original_product_name"]: item["id"]
            for item in items
            if item.get("original_product_name") is not None and item.get("id") is not None
        }

        for original_product_name in original_product_names:
            self._custom_variations_by_product_name.setdefault(original_product_name, [])

    def _flush_custom_product_name_variations_cache(self):
        if self.cosmos_db_client is None:
            return

        for original_product_name, generated_variations in self._pending_generated_variations_by_product_name.items():
            item_id = self._variation_doc_id_by_product_name.get(original_product_name)
            if item_id is None:
                created_id = self.cosmos_db_client.create_item(
                    collection_name="product_name_variations",
                    document={
                        "original_product_name": original_product_name,
                        "generated_product_variations": generated_variations,
                        "custom_product_name_variations": self._custom_variations_by_product_name.get(original_product_name, []),
                    }
                )
                self._variation_doc_id_by_product_name[original_product_name] = str(created_id)
                continue

            self.cosmos_db_client.update_item(
                collection_name="product_name_variations",
                item_id=item_id,
                document={"generated_product_variations": generated_variations},
            )
