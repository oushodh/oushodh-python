from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from typing import Any

import httpx
import pytest

import oushodh
from oushodh import _client

KEY = "oush_test_123"
Handler = Callable[[httpx.Request], httpx.Response]


def medicine(n: int, **extra: Any) -> dict[str, Any]:
    return {
        "id": f"MED-{n:06d}",
        "uuid": f"00000000-0000-0000-0000-{n:012d}",
        "brand": "Napa",
        "category": None,
        "product_name": "Napa 500 mg Tablet",
        "product_image": None,
        "images": [],
        "unit": "Strip",
        "size": "10 Tablets",
        "price": 12.0,
        "price_per": "strip",
        "price_source": "dgda_price",
        "unit_prices": [],
        "prices": {"currency": "BDT", "unit": None, "sizes": [], "strip": None, "packs": []},
        "description_en": None,
        "description_bn": None,
        "dosage_form": "Tablet",
        "strength": "500 mg",
        "generic_name": "Paracetamol",
        "manufacturer": None,
        "source_url": None,
        "last_updated": "2026-11-09T15:27:34Z",
        "dgda_listed": True,
        "medicine_type": "allopathic",
        **extra,
    }


def error(status: int, code: str, message: str = "Something", headers: dict[str, str] | None = None) -> httpx.Response:
    return httpx.Response(status, json={"error": {"code": code, "message": message}}, headers=headers)


def make(handler: Handler, **options: Any) -> oushodh.Oushodh:
    return oushodh.Oushodh(KEY, http_client=httpx.Client(transport=httpx.MockTransport(handler)), **options)


def make_async(handler: Handler, **options: Any) -> oushodh.AsyncOushodh:
    transport = httpx.MockTransport(handler)

    return oushodh.AsyncOushodh(KEY, http_client=httpx.AsyncClient(transport=transport), **options)


class Recorder:
    def __init__(self, *responses: httpx.Response) -> None:
        self.responses = list(responses)
        self.requests: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)

        return self.responses.pop(0)


@pytest.fixture(autouse=True)
def sleeps(monkeypatch: pytest.MonkeyPatch) -> list[float]:
    waited: list[float] = []

    async def async_sleep(seconds: float) -> None:
        waited.append(seconds)

    monkeypatch.setattr(_client, "time", SimpleNamespace(sleep=waited.append))
    monkeypatch.setattr(_client, "asyncio", SimpleNamespace(sleep=async_sleep))
    monkeypatch.delenv("OUSHODH_API_KEY", raising=False)

    return waited


def test_meta_sends_key_and_user_agent() -> None:
    body = {"client": "acme", "id_profile": "default", "medicines": 5000, "last_import": None}
    recorder = Recorder(httpx.Response(200, json=body))

    assert make(recorder).meta() == body

    request = recorder.requests[0]

    assert str(request.url) == "https://api.oushodh.dev/v1/meta"
    assert request.method == "GET"
    assert request.headers["authorization"] == f"Bearer {KEY}"
    assert request.headers["user-agent"] == f"oushodh-python/{oushodh.__version__}"


def test_list_medicines_query() -> None:
    recorder = Recorder(httpx.Response(200, json={"items": [medicine(1)], "next": "abc", "total": 9}))
    page = make(recorder).list_medicines(limit=50, cursor="c1", updated_since="2026-11-08T09:30:00Z", q="napa")

    assert page["next"] == "abc"
    assert page["items"][0]["id"] == "MED-000001"

    url = recorder.requests[0].url

    assert url.path == "/v1/medicines"
    assert dict(url.params) == {"limit": "50", "cursor": "c1", "updated_since": "2026-11-08T09:30:00Z", "q": "napa"}


def test_list_medicines_leaves_out_unset_params() -> None:
    recorder = Recorder(httpx.Response(200, json={"items": [], "next": None, "total": 0}))

    make(recorder).list_medicines()

    assert str(recorder.requests[0].url) == "https://api.oushodh.dev/v1/medicines"


def test_updated_since_datetime_is_sent_in_utc() -> None:
    recorder = Recorder(httpx.Response(200, json={"items": [], "next": None, "total": 0}))
    since = datetime(2026, 11, 8, 15, 30, 0, 123456, tzinfo=timezone(timedelta(hours=6)))

    make(recorder).list_medicines(updated_since=since)

    assert recorder.requests[0].url.params["updated_since"] == "2026-11-08T09:30:00Z"


def test_updated_since_naive_datetime_is_refused() -> None:
    with pytest.raises(ValueError):
        make(Recorder()).list_medicines(updated_since=datetime(2026, 11, 8))


def test_search_query() -> None:
    recorder = Recorder(httpx.Response(200, json={"items": [medicine(1)], "total": 40}))
    result = make(recorder).search("napa 500", limit=5)

    assert result["total"] == 40

    url = recorder.requests[0].url

    assert url.path == "/v1/medicines/search"
    assert dict(url.params) == {"q": "napa 500", "limit": "5"}


def test_get_medicine_path_is_escaped() -> None:
    recorder = Recorder(httpx.Response(200, json=medicine(12933, monograph=None)))
    detail = make(recorder).get_medicine("MED-012933")

    assert detail["monograph"] is None
    assert recorder.requests[0].url.path == "/v1/medicines/MED-012933"

    recorder.responses.append(httpx.Response(200, json=medicine(1, monograph=None)))
    make(recorder).get_medicine("a/b?c")

    assert recorder.requests[1].url.raw_path == b"/v1/medicines/a%2Fb%3Fc"


def test_unknown_fields_are_kept() -> None:
    recorder = Recorder(httpx.Response(200, json=medicine(1, monograph=None, new_field="kept")))
    detail: dict[str, Any] = dict(make(recorder).get_medicine("MED-000001"))

    assert detail["new_field"] == "kept"


def test_medicines_pages_to_the_end() -> None:
    recorder = Recorder(
        httpx.Response(200, json={"items": [medicine(1), medicine(2)], "next": "p2", "total": 5}),
        httpx.Response(200, json={"items": [medicine(3), medicine(4)], "next": "p3", "total": 5}),
        httpx.Response(200, json={"items": [medicine(5)], "next": None, "total": 5}),
    )
    ids = [item["id"] for item in make(recorder).medicines(limit=2, updated_since="2026-11-08T09:30:00Z")]

    assert ids == [f"MED-00000{n}" for n in range(1, 6)]
    assert [r.url.params.get("cursor") for r in recorder.requests] == [None, "p2", "p3"]
    assert all(r.url.params["limit"] == "2" for r in recorder.requests)
    assert all(r.url.params["updated_since"] == "2026-11-08T09:30:00Z" for r in recorder.requests)


def test_images_need_no_key() -> None:
    file = "50d858e0985ecc7f60418aaf0cc5ab587f42c2570a884095a9e8ccacd0f6545c.jpg"
    recorder = Recorder(httpx.Response(200, content=b"\xff\xd8jpeg", headers={"content-type": "image/jpeg"}))
    client = make(recorder)

    assert client.image_url(file) == f"https://api.oushodh.dev/v1/images/{file}"
    assert client.get_image(file) == b"\xff\xd8jpeg"
    assert recorder.requests[0].url.path == f"/v1/images/{file}"
    assert "authorization" not in recorder.requests[0].headers


def test_base_url_option() -> None:
    recorder = Recorder(httpx.Response(200, json={"items": [], "total": 0}))
    client = make(recorder, base_url="http://localhost:8788/")

    client.search("x")

    assert str(recorder.requests[0].url) == "http://localhost:8788/v1/medicines/search?q=x"
    assert client.image_url("a.jpg") == "http://localhost:8788/v1/images/a.jpg"


@pytest.mark.parametrize(
    ("status", "code", "kind"),
    [
        (400, "bad_request", oushodh.BadRequestError),
        (401, "unauthorized", oushodh.AuthenticationError),
        (403, "plan_expired", oushodh.PermissionDeniedError),
        (403, "plan_limit", oushodh.PermissionDeniedError),
        (404, "not_found", oushodh.NotFoundError),
        (429, "rate_limited", oushodh.RateLimitError),
        (429, "quota_exceeded", oushodh.RateLimitError),
        (500, "internal", oushodh.InternalServerError),
    ],
)
def test_error_families(status: int, code: str, kind: type[oushodh.OushodhError]) -> None:
    recorder = Recorder(error(status, code, "For people"))

    with pytest.raises(kind) as caught:
        make(recorder, max_retries=0).get_medicine("MED-1")

    assert isinstance(caught.value, oushodh.OushodhError)
    assert caught.value.status == status
    assert caught.value.code == code
    assert caught.value.message == "For people"


def test_error_body_that_is_not_json() -> None:
    recorder = Recorder(httpx.Response(502, text="<html>Bad gateway</html>"))

    with pytest.raises(oushodh.InternalServerError) as caught:
        make(recorder, max_retries=0).meta()

    assert caught.value.status == 502
    assert caught.value.code is None
    assert caught.value.message == "HTTP 502"


def test_429_waits_retry_after_then_succeeds(sleeps: list[float]) -> None:
    recorder = Recorder(
        error(429, "rate_limited", headers={"Retry-After": "12"}),
        httpx.Response(200, json={"items": [], "total": 0}),
    )

    assert make(recorder).search("napa")["total"] == 0
    assert sleeps == [12.0]
    assert len(recorder.requests) == 2


def test_429_gives_retry_after_when_retries_run_out(sleeps: list[float]) -> None:
    recorder = Recorder(*[error(429, "rate_limited", headers={"Retry-After": "3"}) for _ in range(3)])

    with pytest.raises(oushodh.RateLimitError) as caught:
        make(recorder).meta()

    assert caught.value.retry_after == 3.0
    assert sleeps == [3.0, 3.0]
    assert len(recorder.requests) == 3


def test_quota_exceeded_is_not_retried(sleeps: list[float]) -> None:
    recorder = Recorder(error(429, "quota_exceeded", headers={"Retry-After": "1500000"}))

    with pytest.raises(oushodh.RateLimitError) as caught:
        make(recorder).meta()

    assert caught.value.retry_after == 1500000.0
    assert sleeps == []


def test_5xx_is_retried_then_succeeds(sleeps: list[float]) -> None:
    body = {"client": "acme", "id_profile": "default", "medicines": 1, "last_import": None}
    recorder = Recorder(error(500, "internal"), error(503, "internal"), httpx.Response(200, json=body))

    assert make(recorder).meta()["client"] == "acme"
    assert len(recorder.requests) == 3
    assert len(sleeps) == 2
    assert 0 < sleeps[0] <= sleeps[1] * 2


def test_404_is_not_retried(sleeps: list[float]) -> None:
    recorder = Recorder(error(404, "not_found"))

    with pytest.raises(oushodh.NotFoundError):
        make(recorder).get_medicine("MED-999999")

    assert len(recorder.requests) == 1
    assert sleeps == []


def test_network_errors_are_retried_then_raised(sleeps: list[float]) -> None:
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)

        raise httpx.ConnectError("Connection refused", request=request)

    with pytest.raises(oushodh.APIConnectionError) as caught:
        make(handler).meta()

    assert caught.value.status is None
    assert len(calls) == 3
    assert len(sleeps) == 2


def test_timeout_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timed out", request=request)

    with pytest.raises(oushodh.APITimeoutError):
        make(handler, max_retries=0).meta()


def test_key_never_appears_in_errors_or_repr() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1/meta":
            raise httpx.ConnectError(f"failed with {request.headers['authorization']}", request=request)

        return error(401, "unauthorized", "A valid API key is required")

    client = make(handler, max_retries=0)

    for call in (client.meta, lambda: client.get_medicine("MED-1")):
        with pytest.raises(oushodh.OushodhError) as caught:
            call()

        assert KEY not in str(caught.value)
        assert KEY not in repr(caught.value)
        assert all(KEY not in str(arg) for arg in caught.value.args)

    assert KEY not in repr(client)


def test_key_comes_from_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OUSHODH_API_KEY", KEY)
    recorder = Recorder(httpx.Response(200, json={"items": [], "total": 0}))
    client = oushodh.Oushodh(http_client=httpx.Client(transport=httpx.MockTransport(recorder)))

    client.search("x")

    assert recorder.requests[0].headers["authorization"] == f"Bearer {KEY}"


def test_no_key_fails_at_construction() -> None:
    with pytest.raises(oushodh.OushodhError, match="OUSHODH_API_KEY"):
        oushodh.Oushodh()

    with pytest.raises(oushodh.OushodhError):
        oushodh.AsyncOushodh()


def test_context_manager_closes_its_own_client() -> None:
    with oushodh.Oushodh(KEY) as client:
        pass

    assert client._http.is_closed


@pytest.mark.anyio
async def test_async_routes_and_paging() -> None:
    recorder = Recorder(
        httpx.Response(200, json={"items": [medicine(1)], "next": "p2", "total": 2}),
        httpx.Response(200, json={"items": [medicine(2)], "next": None, "total": 2}),
        httpx.Response(200, json={"items": [medicine(1)], "total": 1}),
        httpx.Response(200, json=medicine(1, monograph=None)),
        httpx.Response(200, content=b"jpeg"),
    )

    async with make_async(recorder) as client:
        ids = [item["id"] async for item in client.medicines(q="napa")]

        assert ids == ["MED-000001", "MED-000002"]
        assert (await client.search("napa"))["total"] == 1
        assert (await client.get_medicine("MED-000001"))["id"] == "MED-000001"
        assert await client.get_image("a.jpg") == b"jpeg"

    assert [r.url.params.get("cursor") for r in recorder.requests[:2]] == [None, "p2"]
    assert all(r.headers["authorization"] == f"Bearer {KEY}" for r in recorder.requests[:4])
    assert "authorization" not in recorder.requests[4].headers


@pytest.mark.anyio
async def test_async_retries_and_errors(sleeps: list[float]) -> None:
    body = {"client": "acme", "id_profile": "default", "medicines": 1, "last_import": None}
    recorder = Recorder(
        error(429, "rate_limited", headers={"Retry-After": "5"}),
        error(500, "internal"),
        httpx.Response(200, json=body),
        error(404, "not_found"),
    )
    client = make_async(recorder)

    assert (await client.meta())["client"] == "acme"
    assert sleeps[0] == 5.0
    assert len(sleeps) == 2

    with pytest.raises(oushodh.NotFoundError) as caught:
        await client.get_medicine("MED-999999")

    assert caught.value.code == "not_found"
    assert len(recorder.requests) == 4
