"""The API's JSON objects, as typed dicts.

Each one is a plain ``dict`` at run time, so fields the API adds later stay in it.
"""

from __future__ import annotations

from typing import Literal, TypedDict

MedicineType = Literal["allopathic", "homoeopathic", "herbal", "ayurvedic", "unani"]


class UnitPrice(TypedDict):
    size: str | None
    price: float


class UnitAmount(TypedDict):
    amount: float
    source: str


class SizeAmount(TypedDict):
    size: str | None
    amount: float
    source: str


class StripAmount(TypedDict):
    amount: float
    units: float | None
    source: str


class PackAmount(TypedDict):
    amount: float
    units: float | None
    label: str
    source: str


class Prices(TypedDict):
    currency: str
    unit: UnitAmount | None
    sizes: list[SizeAmount]
    strip: StripAmount | None
    packs: list[PackAmount]


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


class Monograph(TypedDict):
    source: str
    indications: str | None
    composition: str | None
    pharmacology: str | None
    dosage: str | None
    interactions: str | None
    contraindications: str | None
    side_effects: str | None
    pregnancy_lactation: str | None
    precautions: str | None
    overdose: str | None
    storage: str | None


class MedicineDetail(Medicine):
    monograph: Monograph | None


class Page(TypedDict):
    items: list[Medicine]
    next: str | None
    total: int


class SearchResult(TypedDict):
    items: list[Medicine]
    total: int


class Meta(TypedDict):
    client: str
    id_profile: str
    medicines: int
    last_import: str | None
