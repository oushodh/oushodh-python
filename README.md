# Oushodh for Python

The Python SDK for the Oushodh medicine data API: medicine data for Bangladesh, checked against the DGDA register.

- Python 3.10 or newer.
- One dependency: [httpx](https://www.python-httpx.org/).
- A sync client, `Oushodh`, and an async client, `AsyncOushodh`.
- Fully typed.

The full API reference is at [oushodh.dev/docs](https://oushodh.dev/docs).

## Install

Install from GitHub for now:

```sh
pip install "git+https://github.com/oushodh/oushodh-python.git"
# or
uv add "git+https://github.com/oushodh/oushodh-python.git"
```

Install from PyPI is coming soon (`pip install oushodh`).

## Quickstart

Make an API key on the Keys page of the member portal at [app.oushodh.dev](https://app.oushodh.dev). A key starts
with `oush_` and is shown once. Keep it on your server: a key inside an app can be copied out of it.

```python
from oushodh import Oushodh

client = Oushodh("oush_...")  # or set OUSHODH_API_KEY and call Oushodh()

print(client.meta())  # check that the key works

result = client.search("napa 500", limit=5)

for medicine in result["items"]:
    print(medicine["id"], medicine["product_name"], medicine["prices"]["unit"])

detail = client.get_medicine("MED-012933")
print(detail["monograph"])
```

The client takes these options:

| Option        | Default                   | What it does                                       |
| ------------- | ------------------------- | -------------------------------------------------- |
| `api_key`     | `OUSHODH_API_KEY`         | Your API key. With no key, the client raises.      |
| `base_url`    | `https://api.oushodh.dev` | Where the API is.                                  |
| `timeout`     | `30.0`                    | Seconds to wait for each request.                  |
| `max_retries` | `2`                       | Retries after a `429`, a `5xx` or a network error. |
| `http_client` | a new `httpx.Client`      | Your own `httpx.Client` (`httpx.AsyncClient` for `AsyncOushodh`). |

Close the client when you are done, or use it in a `with` block.

### Async

`AsyncOushodh` has the same methods. Await them, and use `async for` to page.

```python
from oushodh import AsyncOushodh

async with AsyncOushodh() as client:
    async for medicine in client.medicines(q="napa"):
        print(medicine["id"])
```

## Methods

| Method                                                       | Route                          | Returns          |
| ------------------------------------------------------------ | ------------------------------ | ---------------- |
| `meta()`                                                     | `GET /v1/meta`                 | `Meta`           |
| `list_medicines(limit=, cursor=, updated_since=, q=)`        | `GET /v1/medicines`            | `Page`           |
| `medicines(limit=, updated_since=, q=)`                      | `GET /v1/medicines`, each page | medicines, one by one |
| `search(q, limit=)`                                          | `GET /v1/medicines/search`     | `SearchResult`   |
| `get_medicine(ref)`                                          | `GET /v1/medicines/{ref}`      | `MedicineDetail` |
| `image_url(file)`                                            | none                           | the picture's address |
| `get_image(file)`                                            | `GET /v1/images/{file}`        | the picture's bytes |

`ref` is a medicine's ID in any profile, an old ID, or its UUID. The answer always carries the medicine's current ID.

Every model is a typed dict, so it is a plain `dict` at run time. Fields the API adds later are kept in it.

## Paging

`list_medicines()` gives one page: `items`, `next` and `total`. Pass `next` back as `cursor` for the next page. `next`
is `None` on the last page. A page holds 1 to 500 medicines (`limit`, default 100).

`medicines()` does this for you, page after page to the end:

```python
for medicine in client.medicines(limit=500):
    save(medicine)
```

Search has no cursor. To page every match, use `medicines(q=...)`.

## Sync

Copy the whole database once, then fetch only what changed.

1. The first sync pages through `medicines()` to the end. Keep the `last_updated` of the newest medicine.
2. Each later sync passes that time as `updated_since` and pages to the end. Medicines come oldest change first.

```python
since = load_last_sync()  # such as "2026-11-08T09:30:00Z", or None the first time

for medicine in client.medicines(limit=500, updated_since=since):
    upsert(medicine["uuid"], medicine)
    since = max(since or "", medicine["last_updated"])

store_last_sync(since)
```

`updated_since` takes a string like `2026-11-08T09:30:00Z`, or a `datetime` with a timezone. It means "at or after",
so the medicine that set the time comes back once more. Store each medicine by its `uuid`: it never changes. Medicines
are never deleted and IDs are never reused.

## Errors

Every error is an `OushodhError`. It has `status` (the HTTP status), `code` (the API's error code) and `message`.
Match on `code` or on the class, never on `message`: the message is for people and may change.

| Class                   | Status | `code`                           |
| ----------------------- | ------ | -------------------------------- |
| `BadRequestError`       | 400    | `bad_request`                    |
| `AuthenticationError`   | 401    | `unauthorized`                   |
| `PermissionDeniedError` | 403    | `plan_expired` or `plan_limit`   |
| `NotFoundError`         | 404    | `not_found`                      |
| `RateLimitError`        | 429    | `rate_limited` or `quota_exceeded` |
| `InternalServerError`   | 5xx    | `internal`                       |
| `APIConnectionError`    | none   | none: the network failed         |
| `APITimeoutError`       | none   | none: the request timed out      |

```python
from oushodh import NotFoundError, PermissionDeniedError

try:
    medicine = client.get_medicine("MED-012933")
except NotFoundError:
    medicine = None
except PermissionDeniedError as error:
    if error.code == "plan_limit":
        print("Upgrade your plan to read this medicine.")
    raise
```

The SDK retries a `429`, a `5xx` and a network error up to `max_retries` times. After a `5xx` or a network error it
waits a little longer each time. It never retries any other `4xx`: they give the same answer every time. The error
message never holds your key.

## Rate limits

Your plan sets how many requests each key may make in a minute (60 a minute on Developer), and how many your account
may make in a month.

- Over the minute's limit, the API answers `429 rate_limited`. The `Retry-After` header says how many seconds to wait.
  The SDK waits that long and tries again.
- When the month's requests are used up, the API answers `429 quota_exceeded` until the next month. The SDK does not
  retry it. `RateLimitError.retry_after` holds the seconds to the next month.

## Plan limits

Some plans read only the first medicines, in the order of their permanent number. Lists and search leave out the rest.
A lookup by ID of such a medicine raises `PermissionDeniedError` with `code` `plan_limit`. `meta()["medicines"]` says
how many medicines your key reads.

## Images

`product_image` is the address of a medicine's picture. When it is under `/v1/images/`, Oushodh keeps the copy and
serves it with no key, so an `<img>` tag can show it. The file never changes, so it can be cached for a year.

```python
url = medicine["product_image"]

if url and url.startswith(client.image_url("")):
    jpeg = client.get_image(url.rsplit("/", 1)[-1])
```

Any other address belongs to the source, and it can move or be removed.

## Develop

```sh
uv sync
uv run ruff check
uv run ruff format --check
uv run mypy
uv run pytest
```

The tests use `httpx.MockTransport`. They never call the API.

## License

MIT. See [LICENSE](LICENSE).
