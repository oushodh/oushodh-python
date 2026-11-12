from __future__ import annotations

import asyncio
import os
import time
from collections.abc import AsyncIterator, Iterator
from types import TracebackType
from typing import Any, cast
from urllib.parse import quote

import httpx

from ._errors import OushodhError
from ._http import Since, api_error, connection_error, drop_none, list_params, retry_delay
from ._models import Medicine, MedicineDetail, Meta, Page, SearchResult
from ._version import __version__

DEFAULT_BASE_URL = "https://api.oushodh.dev"
DEFAULT_TIMEOUT = 30.0
DEFAULT_MAX_RETRIES = 2


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
        params = list_params(limit, cursor, updated_since, q)

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
        params = drop_none({"q": q, "limit": limit})

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
                error: OushodhError = connection_error(exc)
            else:
                if response.is_success:
                    return response

                error = api_error(response)

            delay = retry_delay(error, attempt, self.max_retries)

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
        params = list_params(limit, cursor, updated_since, q)

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
        params = drop_none({"q": q, "limit": limit})

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
                error: OushodhError = connection_error(exc)
            else:
                if response.is_success:
                    return response

                error = api_error(response)

            delay = retry_delay(error, attempt, self.max_retries)

            if delay is None:
                raise error

            await asyncio.sleep(delay)
            attempt += 1
