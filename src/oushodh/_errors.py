from __future__ import annotations


class OushodhError(Exception):
    """The base of every error the SDK raises.

    ``status`` is the HTTP status and ``code`` the API's error code. Both are ``None`` when no answer came back.
    Match on ``code``, never on ``message``.
    """

    def __init__(self, message: str, *, status: int | None = None, code: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.status = status
        self.code = code


class BadRequestError(OushodhError):
    """400 ``bad_request``."""


class AuthenticationError(OushodhError):
    """401 ``unauthorized``: no key, an unknown key or a revoked key."""


class PermissionDeniedError(OushodhError):
    """403 ``plan_expired`` or ``plan_limit``."""


class NotFoundError(OushodhError):
    """404 ``not_found``."""


class RateLimitError(OushodhError):
    """429 ``rate_limited`` or ``quota_exceeded``. ``retry_after`` is in seconds."""

    def __init__(
        self, message: str, *, status: int | None = None, code: str | None = None, retry_after: float | None = None
    ) -> None:
        super().__init__(message, status=status, code=code)
        self.retry_after = retry_after


class InternalServerError(OushodhError):
    """5xx, such as ``internal``."""


class APIConnectionError(OushodhError):
    """No answer came back: the network failed."""


class APITimeoutError(APIConnectionError):
    """No answer came back in time."""
