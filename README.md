# Oushodh Python SDK

The official Python client for the Oushodh API.

[![CI](https://github.com/oushodh/oushodh-python/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/oushodh/oushodh-python/actions/workflows/ci.yml)
[![Licence: MIT](https://img.shields.io/github/license/oushodh/oushodh-python)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-3776ab)](https://www.python.org/)

## What Oushodh is

Oushodh serves Bangladesh medicine data over a REST API: brands, generics, prices and makers. Make a key in the member
portal at [app.oushodh.dev](https://app.oushodh.dev), and read the docs at [oushodh.dev/docs](https://oushodh.dev/docs).

The SDK needs Python 3.10 or newer. Its one dependency is [httpx](https://www.python-httpx.org/). It has a sync
client, `Oushodh`, and an async client, `AsyncOushodh`, and it is fully typed.

## Install

Install release 0.1.0 from GitHub:

```sh
pip install "git+https://github.com/oushodh/oushodh-python.git@v0.1.0"
# or
uv add "git+https://github.com/oushodh/oushodh-python.git@v0.1.0"
```

Install from PyPI is coming soon.

## Quickstart

Make a key on the Keys page of the member portal. A key starts with `oush_` and is shown once. Keep it on your
server: never put it in a web page or an app.

```sh
export OUSHODH_API_KEY=oush_...
```

```python
from oushodh import Oushodh

client = Oushodh()  # reads OUSHODH_API_KEY

result = client.search("paracetamol", limit=5)

for medicine in result["items"]:
    print(medicine["id"], medicine["product_name"])

medicine = client.get_medicine("MED-012933")
unit = medicine["prices"]["unit"]

print(medicine["product_name"], unit and unit["amount"], "BDT a unit")
```

`Oushodh("oush_...")` takes the key directly. With no key and no `OUSHODH_API_KEY`, it raises an `OushodhError`.

Close the client when you are done, or use it in a `with` block. `AsyncOushodh` has the same methods: await them, and
use `async for` to page.

```python
from oushodh import AsyncOushodh

async with AsyncOushodh() as client:
    async for medicine in client.medicines(q="paracetamol"):
        print(medicine["id"])
```

| Method                                                | Route                          | Returns                |
| ----------------------------------------------------- | ------------------------------ | ---------------------- |
| `meta()`                                              | `GET /v1/meta`                 | `Meta`                 |
| `list_medicines(limit=, cursor=, updated_since=, q=)` | `GET /v1/medicines`            | `Page`                 |
| `medicines(limit=, updated_since=, q=)`               | `GET /v1/medicines`, each page | an iterator of `Medicine` |
| `search(q, limit=)`                                   | `GET /v1/medicines/search`     | `SearchResult`         |
| `get_medicine(ref)`                                   | `GET /v1/medicines/{ref}`      | `MedicineDetail`       |
| `image_url(file)`                                     | none                           | the picture's address  |
| `get_image(file)`                                     | `GET /v1/images/{file}`        | the picture's bytes    |

`meta()` names your account and counts the medicines your plan reads. Call it to check that a key works.

`get_medicine()` takes an ID in any profile, an old ID or a UUID. The answer always carries the medicine's current
ID, and its `monograph`.

Every model is a typed dict, so it is a plain `dict` at run time, with the API's field names. A value no source gives
is `None`. Fields the API adds later are kept in the dict.

## Paging

`list_medicines()` returns one page: `items`, `next` and `total`. Pass `next` back as `cursor` for the next page.
`next` is `None` on the last page. `limit` is 1 to 500, and 100 when you leave it out.

```python
page = client.list_medicines(limit=500)

while True:
    for medicine in page["items"]:
        ...

    if page["next"] is None:
        break

    page = client.list_medicines(limit=500, cursor=page["next"])
```

`medicines()` does the same for you. It yields every medicine and follows `next` to the end:

```python
for medicine in client.medicines(limit=500):
    print(medicine["id"], medicine["product_name"])
```

Search has no cursor. To page through every match, use `medicines(q=...)`.

## Keeping a copy in sync

Copy every medicine once, then fetch only what changed.

1. The first sync pages through every medicine and keeps the newest `last_updated`.
2. Each later sync passes that time as `updated_since` and pages to the end. It gets the medicines changed at or after
   that time, oldest change first.

```python
since = load_last_sync()  # None on the first sync

for medicine in client.medicines(limit=500, updated_since=since):
    save_medicine(medicine["uuid"], medicine)

    if since is None or medicine["last_updated"] > since:
        since = medicine["last_updated"]

save_last_sync(since)
```

- `updated_since` takes a string such as `2026-11-08T09:30:00Z`, or a `datetime` with a timezone. The client sends a
  `datetime` in UTC, to the whole second. A `datetime` with no timezone raises a `ValueError`.
- "At or after" means a change in the same second is never missed. The medicine that set the time comes back once
  more, so save by `uuid`.
- Store `uuid` as the key: it never changes. Show `id` to people.
- Medicines are never deleted and IDs are never reused, so a sync never has to remove one.

## Images

`product_image` is the address of the medicine's picture, or `None`. `images` lists every picture, `product_image`
first. An address under `/v1/images/` is a copy Oushodh keeps. It needs no key, so an `<img>` tag can show it, and it
never changes. Any other address belongs to the source, and it can move or be removed.

`get_image()` takes the file name, not the whole address, and sends no key:

```python
url = medicine["product_image"]

if url and url.startswith(client.image_url("")):
    jpeg = client.get_image(url.rsplit("/", 1)[-1])
```

`image_url(file)` builds the address of a file, such as
`50d858e0985ecc7f60418aaf0cc5ab587f42c2570a884095a9e8ccacd0f6545c.jpg`.

## Errors

Every error is an `OushodhError`. It has `status` (the HTTP status), `code` (the API's error code) and `message`.
Match on the class or on `code`, never on `message`: the message is for people and may change.

| Class                   | Status | `code`                             |
| ----------------------- | ------ | ---------------------------------- |
| `BadRequestError`       | 400    | `bad_request`                      |
| `AuthenticationError`   | 401    | `unauthorized`                     |
| `PermissionDeniedError` | 403    | `plan_expired` or `plan_limit`     |
| `NotFoundError`         | 404    | `not_found`                        |
| `RateLimitError`        | 429    | `rate_limited` or `quota_exceeded` |
| `InternalServerError`   | 5xx    | `internal`                         |
| `APIConnectionError`    | none   | none: the network failed           |
| `APITimeoutError`       | none   | none: the request timed out        |

`APITimeoutError` is an `APIConnectionError`. Both have `status` and `code` set to `None`. When an error body is not
JSON, `code` is `None` and the message is `HTTP <status>`. The key never appears in an error message.

```python
from oushodh import NotFoundError, PermissionDeniedError

try:
    medicine = client.get_medicine("MED-999999")
except NotFoundError:
    medicine = None  # No medicine has that ID.
except PermissionDeniedError as error:
    if error.code != "plan_limit":
        raise

    medicine = None  # The medicine is beyond the medicines your plan reads.
```

## Retries and rate limits

Your plan sets how many requests each key may make in a minute (60 a minute on Developer). It also sets how many
requests your account may make in a month. See [Rate limits](https://oushodh.dev/docs/rate-limits).

- Over the minute's limit, the API answers `429 rate_limited`. The `Retry-After` header says how many seconds to wait.
  The client waits that long and tries again, up to `max_retries` times. After that it raises a `RateLimitError` with
  the seconds in `retry_after`.
- When the month's requests are used up, the API answers `429 quota_exceeded` until the next month. The client never
  retries it. It raises a `RateLimitError` at once, and `retry_after` counts the seconds to the next month.
- After a `5xx`, a network error or a timeout, the client backs off and tries again, up to `max_retries` times. Each
  wait is about twice the last, with a random part, and at most 8 seconds.
- The client never retries a `400`, `401`, `403` or `404`: the same request gets the same answer.

Every route is a `GET`, so a retry is always safe.

## Plan limits

Developer reads the first 5,000 medicines and Team the first 20,000, in the order of their permanent number. Agency
and Custom read all of them.

Lists and search leave out the medicines beyond your plan's number. A lookup by ID of such a medicine answers
`403 plan_limit`: the client raises a `PermissionDeniedError` with `code` `plan_limit`. An account with no active plan
gets `403 plan_expired` on every call.

## Configuration

Pass options to the client as keyword arguments:

```python
client = Oushodh("oush_...", timeout=10.0, max_retries=3)
```

| Option        | Default                   | What it does                                                         |
| ------------- | ------------------------- | -------------------------------------------------------------------- |
| `api_key`     | `OUSHODH_API_KEY`         | Your API key.                                                        |
| `base_url`    | `https://api.oushodh.dev` | Where the API is.                                                    |
| `timeout`     | `30.0`                    | Seconds to wait for each request.                                    |
| `max_retries` | `2`                       | Retries after a `429 rate_limited`, a `5xx` or a network error.      |
| `http_client` | a new `httpx.Client`      | Your own `httpx.Client` (`httpx.AsyncClient` for `AsyncOushodh`).    |

In your own tests, pass an `httpx.Client` with a mock transport, so no request leaves your machine:

```python
import httpx

transport = httpx.MockTransport(
    lambda request: httpx.Response(
        200, json={"client": "acme", "id_profile": "default", "medicines": 1, "last_import": None}
    )
)
client = Oushodh("oush_test_123", http_client=httpx.Client(transport=transport))
```

## Development

```sh
uv sync
uv run ruff check
uv run ruff format --check
uv run mypy
uv run pytest
```

The tests use `httpx.MockTransport`. They never call the API.

## Licence

MIT. Copyright Oushodh. See [LICENSE](LICENSE).
