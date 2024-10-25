class ScrapedProductInfo:
    def __init__(self, name: str, price: float, is_on_promotion: bool, alternative_names: list[str] | None):
        self.name = name
        self.price = price
        self.is_on_promotion = is_on_promotion
        self.alternative_names = alternative_names if alternative_names is not None else []
