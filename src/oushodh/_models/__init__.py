"""The API's JSON objects, as typed dicts.

Each one is a plain ``dict`` at run time, so fields the API adds later stay in it.
"""

from .medicine import Medicine, MedicineDetail, MedicineType
from .meta import Meta
from .monograph import Monograph
from .page import Page, SearchResult
from .prices import PackAmount, Prices, SizeAmount, StripAmount, UnitAmount, UnitPrice

__all__ = [
    "Medicine",
    "MedicineDetail",
    "MedicineType",
    "Meta",
    "Monograph",
    "PackAmount",
    "Page",
    "Prices",
    "SearchResult",
    "SizeAmount",
    "StripAmount",
    "UnitAmount",
    "UnitPrice",
]
