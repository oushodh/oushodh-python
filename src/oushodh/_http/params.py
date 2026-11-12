"""The query of each request."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

Since = str | datetime


def drop_none(params: dict[str, Any]) -> dict[str, Any]:
    return {name: value for name, value in params.items() if value is not None}


def list_params(limit: int | None, cursor: str | None, updated_since: Since | None, q: str | None) -> dict[str, Any]:
    since = format_since(updated_since) if updated_since is not None else None

    return drop_none({"limit": limit, "cursor": cursor, "updated_since": since, "q": q})


def format_since(value: Since) -> str:
    if isinstance(value, str):
        return value

    if value.tzinfo is None:
        raise ValueError("updated_since needs a timezone, such as datetime.now(timezone.utc)")

    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
