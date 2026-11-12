"""The prices of a medicine."""

from __future__ import annotations

from typing import TypedDict


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
