from __future__ import annotations

import os
from typing import Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


DEFAULT_TIMEOUT = 25
DEFAULT_RETRIES = 2
DEFAULT_BACKOFF_FACTOR = 1.0
RETRYABLE_STATUS_CODES = (429, 500, 502, 503, 504)


def _build_proxies(use_proxy: bool) -> dict[str, str] | None:
    if not use_proxy:
        return None

    http_proxy = os.getenv("HTTP_PROXY")
    https_proxy = os.getenv("HTTPS_PROXY")

    if not http_proxy and not https_proxy:
        return None

    return {
        "http": http_proxy or "",
        "https": https_proxy or "",
    }


def _build_session(retries: int, backoff_factor: float) -> requests.Session:
    retry = Retry(
        total=retries,
        connect=retries,
        read=retries,
        status=retries,
        backoff_factor=backoff_factor,
        status_forcelist=RETRYABLE_STATUS_CODES,
        allowed_methods=frozenset({"GET"}),
        raise_on_status=False,
        respect_retry_after_header=True,
    )

    adapter = HTTPAdapter(max_retries=retry)
    session = requests.Session()
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session


def get_json_with_resilience(
    url: str,
    *,
    params: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    timeout: int | tuple[int, int] = DEFAULT_TIMEOUT,
    retries: int = DEFAULT_RETRIES,
    backoff_factor: float = DEFAULT_BACKOFF_FACTOR,
    use_proxy: bool = True,
) -> dict[str, Any] | list[Any] | dict[str, str]:
    proxies = _build_proxies(use_proxy)
    session = _build_session(retries, backoff_factor)

    try:
        response = session.get(
            url,
            params=params,
            headers=headers,
            timeout=timeout,
            proxies=proxies,
        )
        response.raise_for_status()
        return response.json()
    except Exception as e:
        return {
            "_error": f"{type(e).__name__}: {e}",
            "_url": url,
        }
    finally:
        session.close()


def get_text_with_resilience(
    url: str,
    *,
    params: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    timeout: int | tuple[int, int] = DEFAULT_TIMEOUT,
    retries: int = DEFAULT_RETRIES,
    backoff_factor: float = DEFAULT_BACKOFF_FACTOR,
    use_proxy: bool = True,
) -> str:
    proxies = _build_proxies(use_proxy)
    session = _build_session(retries, backoff_factor)

    try:
        response = session.get(
            url,
            params=params,
            headers=headers,
            timeout=timeout,
            proxies=proxies,
        )
        response.raise_for_status()
        return response.text
    except Exception as e:
        return f"__REQUEST_FAILED__: {type(e).__name__}: {e}"
    finally:
        session.close()
