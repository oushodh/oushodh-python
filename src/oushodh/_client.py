from __future__ import annotations

import asyncio
import os
import random
import time
from collections.abc import AsyncIterator, Iterator
from datetime import datetime, timezone
from types import TracebackType
from typing import Any, cast
from urllib.parse import quote

import httpx

from ._errors import (
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
from ._models import Medicine, MedicineDetail, Meta, Page, SearchResult
from ._version import __version__

DEFAULT_BASE_URL = "https://api.oushodh.dev"
DEFAULT_TIMEOUT = 30.0
DEFAULT_MAX_RETRIES = 2

Since = str | datetime


class _BaseClient:
    def __init__(self, api_key: str | None, base_url: str, timeout: float, max_retries: int) -> None:
        key = api_key or os.environ.get("OUSHODH_API_KEY")

        if not key:
            raise OushodhError("No API key: pass api_key or set the OUSHODH_API_KEY environment variable")

        self._api_key = key
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries

    def __repr__(self) -> str:
        return f"{type(self).__name__}(base_url={self.base_url!r})"

    def image_url(self, file: str) -> str:
        """The address of a picture, as ``product_image`` gives it. It needs no key."""

        return f"{self.base_url}/v1/images/{quote(file, safe='')}"

    def _url(self, path: str) -> str:
        return f"{self.base_url}{path}"

    def _headers(self, auth: bool) -> dict[str, str]:
        headers = {"User-Agent": f"oushodh-python/{__version__}"}

        if auth:
            headers["Authorization"] = f"Bearer {self._api_key}"
            headers["Accept"] = "application/json"

        return headers

    def _delay(self, error: OushodhError, attempt: int) -> float | None:
        if attempt >= self.max_retries:
            return None

        # quota_exceeded waits until next month, so it is never retried.
        if isinstance(error, RateLimitError) and error.code != "quota_exceeded":
            return error.retry_after if error.retry_after is not None else _backoff(attempt)

        if isinstance(error, (InternalServerError, APIConnectionError)):
            return _backoff(attempt)

        return None


class Oushodh(_BaseClient):
    """The Oushodh API client.

    ``api_key`` defaults to the ``OUSHODH_API_KEY`` environment variable. Pass ``http_client`` to use your own
    ``httpx.Client``, for example one with a mock transport in tests.
    """

    def __init__(
        self,
        api_key: str | None = None,
        *,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = DEFAULT_TIMEOUT,
        max_retries: int = DEFAULT_MAX_RETRIES,
        http_client: httpx.Client | None = None,
    ) -> None:
        super().__init__(api_key, base_url, timeout, max_retries)
        self._owns_http = http_client is None
        self._http = http_client or httpx.Client()

    def __enter__(self) -> Oushodh:
        return self

    def __exit__(
        self, exc_type: type[BaseException] | None, exc: BaseException | None, tb: TracebackType | None
    ) -> None:
        self.close()

    def close(self) -> None:
        if self._owns_http:
            self._http.close()

    def meta(self) -> Meta:
        return cast(Meta, self._get("/v1/meta").json())

    def list_medicines(
        self,
        *,
        limit: int | None = None,
        cursor: str | None = None,
        updated_since: Since | None = None,
        q: str | None = None,
    ) -> Page:
        params = _list_params(limit, cursor, updated_since, q)

        return cast(Page, self._get("/v1/medicines", params).json())

    def medicines(
        self, *, limit: int | None = None, updated_since: Since | None = None, q: str | None = None
    ) -> Iterator[Medicine]:
        """Every medicine, page after page to the end."""

        cursor: str | None = None

        while True:
            page = self.list_medicines(limit=limit, cursor=cursor, updated_since=updated_since, q=q)

            yield from page["items"]
            cursor = page["next"]

            if cursor is None:
                return

    def search(self, q: str, *, limit: int | None = None) -> SearchResult:
        params = _drop_none({"q": q, "limit": limit})

        return cast(SearchResult, self._get("/v1/medicines/search", params).json())

    def get_medicine(self, ref: str) -> MedicineDetail:
        return cast(MedicineDetail, self._get(f"/v1/medicines/{quote(ref, safe='')}").json())

    def get_image(self, file: str) -> bytes:
        return self._get(f"/v1/images/{quote(file, safe='')}", auth=False).content

    def _get(self, path: str, params: dict[str, Any] | None = None, *, auth: bool = True) -> httpx.Response:
        attempt = 0

        while True:
            try:
                response = self._http.get(
                    self._url(path), params=params, headers=self._headers(auth), timeout=self.timeout
                )
            except httpx.TransportError as exc:
                error: OushodhError = _connection_error(exc)
            else:
                if response.is_success:
                    return response

                error = _api_error(response)

            delay = self._delay(error, attempt)

            if delay is None:
                raise error

            time.sleep(delay)
            attempt += 1


class AsyncOushodh(_BaseClient):
    """The async Oushodh API client. It takes the same options as ``Oushodh``, with an ``httpx.AsyncClient``."""

    def __init__(
        self,
        api_key: str | None = None,
        *,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = DEFAULT_TIMEOUT,
        max_retries: int = DEFAULT_MAX_RETRIES,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        super().__init__(api_key, base_url, timeout, max_retries)
        self._owns_http = http_client is None
        self._http = http_client or httpx.AsyncClient()

    async def __aenter__(self) -> AsyncOushodh:
        return self

    async def __aexit__(
        self, exc_type: type[BaseException] | None, exc: BaseException | None, tb: TracebackType | None
    ) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        if self._owns_http:
            await self._http.aclose()

    async def meta(self) -> Meta:
        return cast(Meta, (await self._get("/v1/meta")).json())

    async def list_medicines(
        self,
        *,
        limit: int | None = None,
        cursor: str | None = None,
        updated_since: Since | None = None,
        q: str | None = None,
    ) -> Page:
        params = _list_params(limit, cursor, updated_since, q)

        return cast(Page, (await self._get("/v1/medicines", params)).json())

    async def medicines(
        self, *, limit: int | None = None, updated_since: Since | None = None, q: str | None = None
    ) -> AsyncIterator[Medicine]:
        """Every medicine, page after page to the end."""

        cursor: str | None = None

        while True:
            page = await self.list_medicines(limit=limit, cursor=cursor, updated_since=updated_since, q=q)

            for item in page["items"]:
                yield item

            cursor = page["next"]

            if cursor is None:
                return

    async def search(self, q: str, *, limit: int | None = None) -> SearchResult:
        params = _drop_none({"q": q, "limit": limit})

        return cast(SearchResult, (await self._get("/v1/medicines/search", params)).json())

    async def get_medicine(self, ref: str) -> MedicineDetail:
        return cast(MedicineDetail, (await self._get(f"/v1/medicines/{quote(ref, safe='')}")).json())

    async def get_image(self, file: str) -> bytes:
        return (await self._get(f"/v1/images/{quote(file, safe='')}", auth=False)).content

    async def _get(self, path: str, params: dict[str, Any] | None = None, *, auth: bool = True) -> httpx.Response:
        attempt = 0

        while True:
            try:
                response = await self._http.get(
                    self._url(path), params=params, headers=self._headers(auth), timeout=self.timeout
                )
            except httpx.TransportError as exc:
                error: OushodhError = _connection_error(exc)
            else:
                if response.is_success:
                    return response

                error = _api_error(response)

            delay = self._delay(error, attempt)

            if delay is None:
                raise error

            await asyncio.sleep(delay)
            attempt += 1


def _drop_none(params: dict[str, Any]) -> dict[str, Any]:
    return {name: value for name, value in params.items() if value is not None}


def _list_params(limit: int | None, cursor: str | None, updated_since: Since | None, q: str | None) -> dict[str, Any]:
    since = _format_since(updated_since) if updated_since is not None else None

    return _drop_none({"limit": limit, "cursor": cursor, "updated_since": since, "q": q})


def _format_since(value: Since) -> str:
    if isinstance(value, str):
        return value

    if value.tzinfo is None:
        raise ValueError("updated_since needs a timezone, such as datetime.now(timezone.utc)")

    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _backoff(attempt: int) -> float:
    return min(0.5 * 2.0**attempt, 8.0) * random.uniform(0.5, 1.0)


def _connection_error(exc: httpx.TransportError) -> APIConnectionError:
    if isinstance(exc, httpx.TimeoutException):
        return APITimeoutError("The request timed out")

    return APIConnectionError(f"Could not reach the API: {type(exc).__name__}")


def _api_error(response: httpx.Response) -> OushodhError:
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
