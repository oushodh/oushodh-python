"""The answers of List medicines and Search."""

from __future__ import annotations

from typing import TypedDict

from .medicine import Medicine


class Page(TypedDict):
    items: list[Medicine]
    next: str | None
    total: int


class SearchResult(TypedDict):
    items: list[Medicine]
    total: int
