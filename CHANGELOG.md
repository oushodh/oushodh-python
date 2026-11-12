# Changelog

## 0.1.0 (unreleased)

- First version of the Python SDK for the Oushodh API `/v1`.
- `Oushodh` and `AsyncOushodh` clients: `meta()`, `list_medicines()`, `medicines()` (pages to the end), `search()`,
  `get_medicine()`, `image_url()` and `get_image()`.
- Typed models for `Medicine`, `MedicineDetail`, `Monograph`, `Page`, `SearchResult` and `Meta`. Unknown fields are kept.
- Errors by family, each with `status`, `code` and `message`.
- Retries on `429 rate_limited` (honours `Retry-After`), `5xx` and network errors.
