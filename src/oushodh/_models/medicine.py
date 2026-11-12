"""One medicine, as lists, search and Get a medicine answer it."""

from __future__ import annotations

from typing import Literal, TypedDict

from .monograph import Monograph
from .prices import Prices, UnitPrice

MedicineType = Literal["allopathic", "homoeopathic", "herbal", "ayurvedic", "unani"]


class Medicine(TypedDict):
    id: str
    uuid: str
    brand: str
    category: str | None
    product_name: str
    product_image: str | None
    images: list[str]
    unit: str | None
    size: str | None
    price: float | None
    price_per: str | None
    price_source: str | None
    unit_prices: list[UnitPrice]
    prices: Prices
    description_en: str | None
    description_bn: str | None
    dosage_form: str | None
    strength: str | None
    generic_name: str | None
    manufacturer: str | None
    source_url: str | None
    last_updated: str
    dgda_listed: bool
    medicine_type: MedicineType | None


class MedicineDetail(Medicine):
    monograph: Monograph | None
