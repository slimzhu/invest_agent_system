from __future__ import annotations

from typing import Any

from app.sources.research_sources import get_brave_search_results


def _search_name(company_name: str, ticker: str) -> str:
    cleaned_name = company_name.strip()
    if not cleaned_name:
        return ticker.upper().strip()
    return cleaned_name


def get_ir_and_transcript_links(company_name: str, ticker: str) -> dict[str, Any]:
    search_name = _search_name(company_name, ticker)
    ticker_upper = ticker.upper().strip()
    prefix = search_name if search_name == ticker_upper else f"{search_name} {ticker_upper}"
    queries = [
        f'{prefix} investor relations earnings transcript',
        f'{prefix} investor presentation pdf',
        f'{prefix} quarterly results investor relations',
    ]

    results: list[dict[str, Any]] = []
    for q in queries:
        res = get_brave_search_results(q, count=3)
        if res.get("enabled"):
            results.append(res)

    return {
        "source_name": "ir_and_transcript_links",
        "enabled": True,
        "ticker": ticker_upper,
        "search_name": search_name,
        "queries": queries,
        "results": results,
    }
