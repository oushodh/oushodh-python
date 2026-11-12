from __future__ import annotations

from oushodh import APIConnectionError, InternalServerError, NotFoundError, RateLimitError
from oushodh._http import retry_delay


def test_rate_limited_waits_retry_after() -> None:
    error = RateLimitError("slow down", status=429, code="rate_limited", retry_after=7)

    assert retry_delay(error, 0, 2) == 7


def test_quota_exceeded_and_404_are_not_retried() -> None:
    quota = RateLimitError("used up", status=429, code="quota_exceeded", retry_after=3600)
    missing = NotFoundError("missing", status=404, code="not_found")

    assert retry_delay(quota, 0, 2) is None
    assert retry_delay(missing, 0, 2) is None


def test_server_and_network_errors_back_off() -> None:
    for error in (InternalServerError("down", status=503), APIConnectionError("no answer")):
        for attempt in range(3):
            delay = retry_delay(error, attempt, 5)

            assert delay is not None
            assert 0.25 * 2**attempt <= delay <= 0.5 * 2**attempt


def test_no_retry_past_max_retries() -> None:
    assert retry_delay(InternalServerError("down", status=503), 2, 2) is None
