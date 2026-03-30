"""Reusable retry decorator for async HTTP and LLM calls."""

import os
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)
import aiohttp

MAX_RETRIES = int(os.getenv("MAX_RETRIES", "3"))
RETRY_BACKOFF = float(os.getenv("RETRY_BACKOFF", "2.0"))


def with_retry(func):
    """Wrap an async function with exponential-backoff retry on transient errors."""
    return retry(
        stop=stop_after_attempt(MAX_RETRIES),
        wait=wait_exponential(multiplier=RETRY_BACKOFF, min=1, max=30),
        retry=retry_if_exception_type(
            (aiohttp.ClientError, TimeoutError, ConnectionError)
        ),
        reraise=True,
    )(func)
