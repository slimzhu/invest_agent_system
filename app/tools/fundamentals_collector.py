from __future__ import annotations

from typing import Any

from app.config import settings
from app.sources.filings_sources import (
    extract_key_company_facts,
    get_sec_company_facts,
)
from app.tools.filings_collector import get_cik_for_ticker
from app.utils.http_utils import get_json_with_resilience


def _safe_get_json(url, params=None, headers=None):
    data = get_json_with_resilience(
        url,
        params=params,
        headers=headers,
        timeout=(10, 30),
        retries=2,
        use_proxy=True,
    )
    if isinstance(data, dict) and data.get("_error"):
        print(f"[WARN] API failed: {data['_error']}")
        return {}
    return data

def get_finnhub_basic_financials(symbol: str) -> dict[str, Any]:
    if not settings.FINNHUB_API_KEY:
        return {
            "enabled": False,
            "reason": "FINNHUB_API_KEY missing",
            "symbol": symbol,
            "metric": {},
            "series": {},
        }

    url = "https://finnhub.io/api/v1/stock/metric"
    params = {
        "symbol": symbol.upper().strip(),
        "metric": "all",
        "token": settings.FINNHUB_API_KEY,
    }

    data = _safe_get_json(url, params=params)

    return {
        "enabled": bool(data.get("metric") or data.get("series")),
        "symbol": symbol.upper().strip(),
        "metric": data.get("metric", {}),
        "series": data.get("series", {}),
        "error": None if data else "API failed or empty response",
    }


def get_finnhub_quote(symbol: str) -> dict[str, Any]:
    if not settings.FINNHUB_API_KEY:
        return {
            "enabled": False,
            "reason": "FINNHUB_API_KEY missing",
            "symbol": symbol,
        }

    url = "https://finnhub.io/api/v1/quote"
    params = {
        "symbol": symbol.upper().strip(),
        "token": settings.FINNHUB_API_KEY,
    }

    data = _safe_get_json(url, params=params)

    return {
        "enabled": bool(data),
        "symbol": symbol.upper().strip(),
        "quote": data,
        "error": None if data else "API failed or empty response",
    }


def collect_structured_fundamentals(ticker: str) -> dict[str, Any]:
    ticker = ticker.upper().strip()

    basic_financials = get_finnhub_basic_financials(ticker)
    quote = get_finnhub_quote(ticker)

    cik = get_cik_for_ticker(ticker)
    sec_facts_summary: dict[str, Any] = {}

    if cik:
        company_facts = get_sec_company_facts(cik)
        sec_facts_summary = extract_key_company_facts(company_facts)

    return {
        "ticker": ticker,
        "basic_financials": basic_financials,
        "quote": quote,
        "sec_facts_summary": sec_facts_summary,
    }
