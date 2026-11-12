"""When to try a request again, and how long to wait first."""

from __future__ import annotations

import random

from .._errors import APIConnectionError, InternalServerError, OushodhError, RateLimitError


def retry_delay(error: OushodhError, attempt: int, max_retries: int) -> float | None:
    """Seconds to wait before the next try, or ``None`` when the error must not be retried."""

    if attempt >= max_retries:
        return None

    # quota_exceeded waits until next month, so it is never retried.
    if isinstance(error, RateLimitError) and error.code != "quota_exceeded":
        return error.retry_after if error.retry_after is not None else backoff(attempt)

    if isinstance(error, (InternalServerError, APIConnectionError)):
        return backoff(attempt)

    return None


def backoff(attempt: int) -> float:
    return min(0.5 * 2.0**attempt, 8.0) * random.uniform(0.5, 1.0)
