import json
import logging

from files.file_worker import FileWorker, RowInfo, WorkerProgress


class ProductInfo:
    def __init__(self, product_name: str, quantity: int):
        self.product_name = product_name
        self.quantity = quantity


class JsonContentWorker(FileWorker):
    """
    This worker handles JSON content of the file_data message property
    The JSON format should be:
    {"rows": [{"product_name": "product 1", "quantity": 10}, {"product_name": "product 2", "quantity": 20}]}
    """
    def __init__(self):
        self.json_data: dict | None = None
        self.current_row = 0
        self.total_rows = 0
        # This set is needed in order to ignore duplicate products in our input file
        self.met_products = set()
        pass

    def open_file(self, json_str: dict):
        try:
            self.json_data = json_str
        except json.JSONDecodeError:
            raise ValueError("The JSON content is not valid")

        self.total_rows = len(self.json_data["rows"])

    def validate_input(self):
        if self.json_data is None:
            raise ValueError("The JSON content is not loaded")

        if not all(isinstance(row, dict) for row in self.json_data["rows"]):
            raise ValueError("All rows must be dictionaries")

    def get_next_row(self) -> RowInfo:
        if self.json_data is None:
            raise Exception("The JSON content is not loaded")

        while self.current_row < self.total_rows:
            logging.info("JsonContentWOrker: Reading row %d from %d", self.current_row, self.total_rows)
            current_row = self.current_row
            self.current_row += 1

            self.original_product_name, currentProductNameVariations = self._generateProductNameVariations(
                self.json_data["rows"][current_row].get("product_name")
                )
            # If the products has been met, ignore it and continue to the next row
            if (self.original_product_name not in self.met_products):
                try:
                    value = self.json_data["rows"][current_row].get("quantity")
                    self.currentProductQuantity = int(value)  # type: ignore
                except TypeError:
                    # The quantity of the product is most probably empty. Skip this row
                    # TODO: Do this through the worker somehow
                    # self.add_not_bought_product(self.original_product_name, -1)
                    continue
                self.met_products.add(self.original_product_name)
                return RowInfo(self.original_product_name, currentProductNameVariations, self.currentProductQuantity)
            else:
                logging.info("ExcelWorker: Skipping duplicate product: " + self.original_product_name)

        return RowInfo(None, None, None)

    def get_progress(self) -> WorkerProgress:
        return WorkerProgress(self.original_product_name, self.current_row, self.total_rows)
