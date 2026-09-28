"""Errors raised by the model layer."""
from __future__ import annotations


class BudgetExceeded(RuntimeError):
    """A call was refused because spend + in-flight reservations + this call's worst case would pass a cap."""


class TransientError(RuntimeError):
    """A retryable provider failure (timeouts, 408/429/5xx)."""


class ProviderError(RuntimeError):
    """A non-retryable provider failure (bad request, auth, key limit, retries exhausted)."""


class MissingKeyError(RuntimeError):
    """An API key is needed for a live call but is not configured."""
