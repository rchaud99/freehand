"""The model layer: OpenRouter (and the historical direct-Gemini route), a request cache, a spend ledger with hard
budget caps, and the model registry."""
from freehand.llm.adapter import Adapter, Reply
from freehand.llm.cache import RequestCache
from freehand.llm.errors import BudgetExceeded, MissingKeyError, ProviderError, TransientError
from freehand.llm.fake import FakeAdapter
from freehand.llm.ledger import Budget, EpisodeBudget, Ledger
from freehand.llm.registry import ModelSpec, Registry, load_registry, make_adapter

__all__ = ["Adapter", "Budget", "BudgetExceeded", "EpisodeBudget", "FakeAdapter", "Ledger", "MissingKeyError",
           "ModelSpec", "ProviderError", "Registry", "Reply", "RequestCache", "TransientError", "load_registry",
           "make_adapter"]
