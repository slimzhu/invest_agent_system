from __future__ import annotations

import asyncio
from typing import Any

from agents import Runner
from openai import APIConnectionError, APITimeoutError, APIStatusError


RETRYABLE_STATUS_CODES = {408, 409, 429, 500, 502, 503, 504}


def _is_retryable_error(exc: Exception) -> bool:
    if isinstance(exc, (APIConnectionError, APITimeoutError)):
        return True

    if isinstance(exc, APIStatusError):
        return exc.status_code in RETRYABLE_STATUS_CODES

    message = str(exc).lower()
    retry_markers = (
        "connection error",
        "remoteprotocolerror",
        "incomplete chunked read",
        "peer closed connection",
        "connecterror",
        "read timed out",
        "connection reset by peer",
    )
    return any(marker in message for marker in retry_markers)


async def run_agent_with_retry(
    agent: Any,
    input_data: str,
    *,
    context: Any | None = None,
    max_attempts: int = 5,
    base_delay_seconds: float = 2.0,
) -> Any:
    last_exc: Exception | None = None

    for attempt in range(1, max_attempts + 1):
        try:
            if context is None:
                return await Runner.run(agent, input_data)
            return await Runner.run(agent, input_data, context=context)
        except Exception as exc:
            last_exc = exc
            if attempt >= max_attempts or not _is_retryable_error(exc):
                raise

            delay = base_delay_seconds * attempt
            print(
                f"[WARN] Agent run transient failure on attempt {attempt}/{max_attempts}: "
                f"{type(exc).__name__}: {exc}. Retrying in {delay:.1f}s..."
            )
            await asyncio.sleep(delay)

    if last_exc is not None:
        raise last_exc

    raise RuntimeError("run_agent_with_retry failed without raising an exception")
