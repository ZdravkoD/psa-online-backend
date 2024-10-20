

import re
from typing import List


class RowInfo:
    def __init__(self, original_product_name: str | None, product_name_variations: List[str] | None, product_quantity: int | None):
        self.original_product_name = original_product_name
        self.product_name_variations = product_name_variations if product_name_variations is not None else []
        self.custom_product_name_variations: List[str] = []
        self.product_quantity = product_quantity

    def __str__(self) -> str:
        return str(self.__dict__)


class WorkerProgress:
    def __init__(self, original_product_name, current_input_row, total_number_of_rows):
        self.original_product_name = original_product_name
        self.current_input_row = current_input_row
        self.total_number_of_rows = total_number_of_rows

    def to_json(self):
        return {
            "original_product_name": self.original_product_name,
            "current_input_row": self.current_input_row,
            "total_number_of_rows": self.total_number_of_rows
        }

    @staticmethod
    def from_json(json_data):
        return WorkerProgress(
            json_data["original_product_name"],
            json_data["current_input_row"],
            json_data["total_number_of_rows"]
        )

    def __str__(self):
        return str(self.to_json())

    def __repr__(self):
        return self.__str__()


class FileWorker:
    """
    This is the base class for all worker types on the task file_data message
    """

    def __init__(self):
        pass

    def open_file(self, _: str):
        raise NotImplementedError("Subclasses must implement this method")

    def validate_input(self):
        raise NotImplementedError("Subclasses must implement this method")

    def get_next_row(self) -> RowInfo:
        raise NotImplementedError("Subclasses must implement this method")

    def get_progress(self) -> WorkerProgress:
        raise NotImplementedError("Subclasses must implement this method")

    def _generateProductNameVariations(self, productName: str):
        result = []
        # точката (гр.|мг. и т.н.) се заменя с интервал
        # Десетичната запетая се заменя с точка
        productName_xWithSpaces = productName.lower()\
            .strip()\
            .replace(".", " ")\
            .replace("/", " ")\
            .replace("!", "")\
            .replace(",", ".")

        # define desired replacements
        rep = {"x ": "x",  # English x
               "х ": "х"}  # Българско х
        # use these three lines to do the replacement
        rep = dict((re.escape(k), v) for k, v in rep.items())
        pattern = re.compile("|".join(rep.keys()))
        productName_xWithoutSpaces = pattern.sub(lambda m: rep[re.escape(m.group(0))], productName_xWithSpaces)

        productName_withoutX = productName_xWithoutSpaces.replace("x", "").replace("х", "")

        productName_withoutTabletki = productName_xWithSpaces.replace("x", "")\
            .replace("х", "")\
            .replace("табл", "")\
            .replace("таб", "")\
            .replace("тбл", "")\
            .replace("тб ", "")

        productName_withoutUf = productName_withoutTabletki.replace("уф", "")
        productName_withShortGrams = re.sub(r"гр(?=\s|$)", "г", productName_withoutUf)
        productName_withShortMilligrams = re.sub(r"мг(?=.*мг)", "", productName_withShortGrams)
        productName_replacedSasheta = productName_withShortMilligrams.replace("сашета", "сашети")
        productName_replacedSasheta2 = productName_withShortMilligrams.replace("сашета", "саш")
        productName_replacedSasheta3 = productName_withShortMilligrams.replace("сашета", "саше")

        result.append(productName_withoutTabletki)  # 1
        result.append(productName_xWithoutSpaces)  # 2
        result.append(productName_xWithSpaces)  # 3
        result.append(productName_withoutX)  # 4
        result.append(productName_withoutUf)  # 5
        result.append(productName_withShortGrams)  # 6
        result.append(productName_withShortMilligrams)  # 7
        result.append(productName_replacedSasheta)  # 8
        result.append(productName_replacedSasheta2)
        result.append(productName_replacedSasheta3)

        # make result to contain only unique strings
        result = self._uniqueList(result)
        return productName, result

    # We need this custom method in order to retain the order of the elements
    def _uniqueList(self, myList: list):
        # initialize a null list
        unique_list = []

        # traverse for all elements
        for x in myList:
            # check if exists in unique_list or not
            if x not in unique_list:
                unique_list.append(x)

        return unique_list
