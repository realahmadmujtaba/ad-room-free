"""Retry helper for transient Gemini overload.

`503 UNAVAILABLE` ("model is currently experiencing high demand") and
`429 RESOURCE_EXHAUSTED` are transient on Google's side, not app bugs — retry
with exponential backoff before surfacing them to the user.
"""
import asyncio
import random
import time

from google.genai import errors as genai_errors

RETRYABLE_CODES = {429, 503}
ATTEMPTS = 4
BASE_DELAY = 2.0


def is_retryable(exc: BaseException) -> bool:
    return getattr(exc, "code", None) in RETRYABLE_CODES


def _delay(attempt: int) -> float:
    return BASE_DELAY * (2**attempt) + random.uniform(0, 1)


def call_with_retry(fn, *args, **kwargs):
    """Call fn(*args, **kwargs), retrying transient Gemini overload errors."""
    last_exc = None
    for attempt in range(ATTEMPTS):
        try:
            return fn(*args, **kwargs)
        except genai_errors.APIError as exc:
            last_exc = exc
            if not is_retryable(exc) or attempt == ATTEMPTS - 1:
                raise
            time.sleep(_delay(attempt))
    raise last_exc


def call_with_model_fallback(fn, models, *, model_kwarg="model", **kwargs):
    """Call fn(**{model_kwarg: model}, **kwargs) for the first model in
    `models`, retrying transient overload; if that model's retries are fully
    exhausted, fall through to the next model in the list instead of failing.
    """
    last_exc = None
    for i, model in enumerate(models):
        try:
            return call_with_retry(fn, **{model_kwarg: model}, **kwargs)
        except genai_errors.APIError as exc:
            last_exc = exc
            if not is_retryable(exc) or i == len(models) - 1:
                raise
    raise last_exc


async def call_async_with_retry(fn, *args, **kwargs):
    """Async version of call_with_retry."""
    last_exc = None
    for attempt in range(ATTEMPTS):
        try:
            return await fn(*args, **kwargs)
        except genai_errors.APIError as exc:
            last_exc = exc
            if not _is_retryable(exc) or attempt == ATTEMPTS - 1:
                raise
            await asyncio.sleep(_delay(attempt))
    raise last_exc
