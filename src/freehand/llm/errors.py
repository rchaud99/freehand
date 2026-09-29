"""Errors raised by the model layer."""
from __future__ import annotations

from freehand.errors import FreehandError


class BudgetExceeded(FreehandError, RuntimeError):
    """A call was refused because spend + in-flight reservations + this call's worst case would pass a cap."""


class TransientError(FreehandError, RuntimeError):
    """A retryable provider failure (timeouts, 408/429/5xx)."""


class ProviderError(FreehandError, RuntimeError):
    """A non-retryable provider failure (bad request, auth, key limit, retries exhausted)."""


class MissingKeyError(FreehandError, RuntimeError):
    """An API key is needed for a live call but is not configured."""
