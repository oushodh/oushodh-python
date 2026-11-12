"""The account a key belongs to."""

from __future__ import annotations

from typing import TypedDict


class Meta(TypedDict):
    client: str
    id_profile: str
    medicines: int
    last_import: str | None
