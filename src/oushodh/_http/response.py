"""Turns a failed answer, or no answer, into the matching error."""

from __future__ import annotations

import httpx

from .._errors import (
    APIConnectionError,
    APITimeoutError,
    AuthenticationError,
    BadRequestError,
    InternalServerError,
    NotFoundError,
    OushodhError,
    PermissionDeniedError,
    RateLimitError,
)


def connection_error(exc: httpx.TransportError) -> APIConnectionError:
    if isinstance(exc, httpx.TimeoutException):
        return APITimeoutError("The request timed out")

    return APIConnectionError(f"Could not reach the API: {type(exc).__name__}")


def api_error(response: httpx.Response) -> OushodhError:
    status = response.status_code
    code: str | None = None
    message = f"HTTP {status}"

    try:
        body = response.json()
    except ValueError:
        body = None

    detail = body.get("error") if isinstance(body, dict) else None

    if isinstance(detail, dict):
        code = detail.get("code") if isinstance(detail.get("code"), str) else None
        message = detail["message"] if isinstance(detail.get("message"), str) else message

    if status == 429:
        return RateLimitError(message, status=status, code=code, retry_after=_retry_after(response))

    kind = _KINDS.get(status, InternalServerError if status >= 500 else OushodhError)

    return kind(message, status=status, code=code)


def _retry_after(response: httpx.Response) -> float | None:
    try:
        return float(response.headers["retry-after"])
    except (KeyError, ValueError):
        return None


_KINDS: dict[int, type[OushodhError]] = {
    400: BadRequestError,
    401: AuthenticationError,
    403: PermissionDeniedError,
    404: NotFoundError,
}
