from typing import NamedTuple


class ScrapedProductInfo(NamedTuple):
    name: str
    price: float
    is_on_promotion: bool
