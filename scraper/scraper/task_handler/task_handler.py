import json
import logging
import math
from typing import List

from selenium.common.exceptions import StaleElementReferenceException
from shared_lib.messaging.messaging import ScraperTaskItem
from pharmacy_distributors.common.browser_common import BrowserCommon
from pharmacy_distributors.sting.sting import StingPharma
from pharmacy_distributors.phoenix.phoenix_optimized import PhoenixPharmaOptimized
from files.file_worker import FileWorker, RowInfo
from files.file_worker_factory import FileWorkerFactory
from files.azure_blob_client import AzureBlobClient
from task_handler.task_update_publisher import TaskUpdatePublisher


class ProductInfo:
    def __init__(self, scraper: BrowserCommon, name: str, price: float):
        self.scraper = scraper
        self.name = name
        self.price = price

        if self.scraper is None:
            raise ValueError("Scraper must not be None")
        if not isinstance(name, str):
            raise ValueError("Product name must be a string")
        if not isinstance(price, float):
            raise ValueError("Product price must be a float")

    # string representation of the object
    def __str__(self):
        return f"ProductInfo(scraper={self.scraper}, name={self.name}, price={self.price})"

    def __dict__(self):
        return {
            "distributor": self.scraper.name,
            "name": self.name,
            "price": self.price
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
            raise ValueError("All pharmacy product infos must be a list of ProductInfo")
        if not isinstance(bought_from_distributor, str):
            raise ValueError("Bought from pharmacy must be a string")

    def __dict__(self):
        return {
            "original_product_name": self.original_product_name,
            "all_pharmacy_product_infos": [product_info.__dict__() for product_info in self.all_pharmacy_product_infos],
            "bought_from_distributor": self.bought_from_distributor
        }


class UnboughtProductInfo:
    def __init__(self, product_name: str, quantity: int):
        self.product_name = product_name
        self.quantity = quantity

        if not isinstance(product_name, str):
            raise ValueError("Product name must be a string")
        if not isinstance(quantity, int):
            raise ValueError("Quantity must be an integer")

    def __dict__(self):
        return {
            "product_name": self.product_name,
            "quantity": self.quantity
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
        try:
            self.taskItem = taskItem
            self.file_worker: FileWorker = FileWorkerFactory(taskItem.file_type).get_file_worker()
            self.task_update_publisher = TaskUpdatePublisher()
            self.scrapers = self._get_scrapers()
            self.bought_products: List[BoughtProductInfo] = []
            self.unbought_products: List[UnboughtProductInfo] = []
        except Exception as e:
            logging.error("TaskHandler: Couldn't initialize the task handler: ", e)
            self.task_update_publisher.publish_error(
                self.taskItem.account_id,
                self.taskItem.id,
                "Couldn't initialize the task handler",
                str(e),
                0)
            raise e

    def handle_task(self):
        logging.info("Handling task: ", self.taskItem.to_json())
        try:
            self._open_and_validate_input_file()
            for scraper in self.scrapers:
                scraper.login()
                scraper.prepare_for_order()

            self._work_loop()

            self.task_update_publisher.publish_final_report(
                self.taskItem.account_id,
                self.taskItem.id,
                json.dumps(self._generate_report().__dict__()),
                100)
        except Exception as e:
            logging.exception("TaskHandler: Failed to handle the task: ", str(e))
            self.task_update_publisher.publish_error(
                self.taskItem.account_id,
                self.taskItem.id,
                "Failed to handle the task",
                str(e) if str(e).strip() != "" else str(e.__traceback__),
                0)
            return
        finally:
            print("FINALLLYYYYY")
            for scraper in self.scrapers:
                # print("Saving screenshot for scaper: ", scraper.get_name())
                # scraper.saveScreenshot()
                screenshotPng, screenshotName = scraper.getScreenshot()
                AzureBlobClient().upload_blob_to_output_container(screenshotName, screenshotPng)

    def _get_scrapers(self) -> List[BrowserCommon]:
        scrapers: List[BrowserCommon] = []

        for distributor in self.taskItem.distributors:
            if distributor == "sting":
                logging.info("TaskHandler: Handling task for Sting")
                scrapers.append(StingPharma(self.taskItem.pharmacy_id))
            elif distributor == "phoenix":
                logging.info("TaskHandler: Handling task for Phoenix")
                scrapers.append(PhoenixPharmaOptimized(self.taskItem.pharmacy_id))

        return scrapers

    def _open_and_validate_input_file(self):
        try:
            self.file_worker.open_file(self.taskItem.file_data)
        except Exception as e:
            logging.error("TaskHandler: Couldn't open the file: ", e)
            self.task_update_publisher.publish_error(
                self.taskItem.account_id,
                self.taskItem.id,
                "Couldn't open the file: " + self.taskItem.file_name,
                str(e),
                0)
            raise e

        try:
            self.file_worker.validate_input()
        except Exception as e:
            logging.error("TaskHandler: Couldn't validate the input file: ", e)
            self.task_update_publisher.publish_error(
                self.taskItem.account_id,
                self.taskItem.id,
                "Couldn't validate the input file: " + self.taskItem.file_name,
                str(e),
                0)
            raise e

    def _work_loop(self):
        while True:
            try:
                row_info: RowInfo = self.file_worker.get_next_row()
            except Exception as e:
                logging.error("TaskHandler: Couldn't get next row: ", e)
                self.task_update_publisher.publish_error(self.taskItem.account_id, self.taskItem.id, "Couldn't get next row", str(e), 0)
                raise e
            if row_info.product_name_variations is None or row_info.product_quantity is None:
                logging.info("TaskHandler: No more rows to process: ", str(row_info))
                break

            progress = self.file_worker.get_progress()
            progress_percent = math.floor(progress.current_input_row / progress.total_number_of_rows * 100)
            self.task_update_publisher.publish_progress_update(
                self.taskItem.account_id,
                self.taskItem.id,
                json.dumps(progress.to_json()),
                progress_percent)

            self.buy_lowest_price_for_product(progress.original_product_name, row_info.product_name_variations, row_info.product_quantity)
        self.task_update_publisher.publish_success(
            self.taskItem.account_id,
            self.taskItem.id,
            "Задачата приключи успешно!",
            100)

    def buy_lowest_price_for_product(self, productName: str, productSearchNames: list, quantity: int):
        logging.info("Getting prices for: %s", productName)
        all_product_prices: List[ProductInfo] = self._get_all_prices(productSearchNames)
        best_product: ProductInfo | None = None
        for product in all_product_prices:
            logging.info("Product: %s, Price: %f", product.name, product.price)
            if best_product is None or product.price < best_product.price:
                best_product = product
            elif product.price == best_product.price:
                if product.scraper.get_priority() < best_product.scraper.get_priority():
                    best_product = product

        if best_product is None:
            logging.error("Couldn't find product: " + productName)
            self._store_unbought_product(productName, quantity)
            return

        logging.info("Best product: %s, Price: %f, added To %s", best_product.name, best_product.price, best_product.scraper.get_name())
        if product.scraper.add_product_to_cart(best_product.name, quantity):
            self._store_bought_product(productName, all_product_prices, product.scraper.get_name())
        else:
            logging.error("Product found, but couldn\'t be added to cart: " + productName)
            self._store_unbought_product(productName, quantity)

    def _get_all_prices(self, productSearchNames: list) -> List[ProductInfo]:
        print("TaskHandler: Getting all prices for: ", productSearchNames)
        for scraper in self.scrapers:
            result: List[ProductInfo] = []
            try:
                name, price = scraper.get_product_name_and_price(productSearchNames)
            except StaleElementReferenceException:
                # retry
                scraper.refresh_page()
                try:
                    name, price = scraper.get_product_name_and_price(productSearchNames)
                except Exception as e:
                    logging.error("TaskHandler: Couldn't get product name and price: ", e)
                    continue
            if price != math.inf:
                result.append(ProductInfo(scraper, name, price))

        # print("TaskHandler: All prices: ", str(result))
        print("TaskHandler: All prices:", [(info.scraper, info.name, info.price) for info in result])
        return result

    def _store_bought_product(self, original_product_name: str, all_pharmacy_product_infos: List[ProductInfo], bought_from_distributor: str):
        bought_product = BoughtProductInfo(original_product_name, all_pharmacy_product_infos, bought_from_distributor)
        self.bought_products.append(bought_product)

    def _store_unbought_product(self, product_name: str, quantity: int):
        unbought_product = UnboughtProductInfo(product_name, quantity)
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
                        price=product_info.price
                     ) for product_info in bought_product.all_pharmacy_product_infos
                ],
                bought_from_distributor=bought_product.bought_from_distributor
            )
            report.bought_products.append(bought_product_dict)

        for unbought_product in self.unbought_products:
            unbought_product_dict = UnboughtProductInfo(
                product_name=unbought_product.product_name,
                quantity=unbought_product.quantity
            )
            report.unbought_products.append(unbought_product_dict)

        return report
