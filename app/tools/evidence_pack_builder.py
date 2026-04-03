import copy
from typing import Any

from app.sources.news_sources import get_company_news
from app.sources.market_sources import get_market_snapshot
from app.sources.ir_sources import get_ir_and_transcript_links
from app.tools.company_data import get_company_profile
from app.tools.filings_collector import (
    collect_filing_analysis,
    collect_recent_primary_filings,
)
from app.tools.fundamentals_collector import collect_structured_fundamentals


def _count_source_items(source_data: dict[str, Any], item_keys: list[str]) -> int:
    for key in item_keys:
        value = source_data.get(key)
        if isinstance(value, list):
            return len(value)
        if isinstance(value, dict):
            return len(value)
    return 0


def _summarize_company_source(source_data: Any, item_keys: list[str]) -> dict[str, Any]:
    if not isinstance(source_data, dict):
        return {
            "enabled": False,
            "item_count": 0,
            "error": "Invalid source payload",
        }

    enabled = bool(source_data.get("enabled", True))
    item_count = _count_source_items(source_data, item_keys)
    return {
        "enabled": enabled,
        "item_count": item_count,
        "error": source_data.get("error") or source_data.get("reason"),
    }


def _build_data_availability_summary(
    evidence_by_theme: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    source_keys = {
        "company_profile": ["key_risks"],
        "company_news": ["articles"],
        "recent_filings": ["recent_10k_10q_8k"],
        "filing_analysis": ["filing_analysis"],
        "structured_fundamentals": ["basic_financials", "quote", "sec_facts_summary"],
        "ir_and_transcript_links": ["results"],
        "market_snapshot": [],
    }

    overall = {
        "companies": 0,
        "sources": {
            source_name: {"available": 0, "missing": 0}
            for source_name in source_keys
        },
    }
    by_theme: dict[str, Any] = {}

    for theme_name, companies in evidence_by_theme.items():
        theme_summary = {
            "company_count": len(companies),
            "companies": [],
        }

        for company in companies:
            overall["companies"] += 1
            ticker = company.get("ticker", "")
            source_status: dict[str, Any] = {}

            for source_name, item_keys in source_keys.items():
                summary = _summarize_company_source(company.get(source_name, {}), item_keys)
                source_status[source_name] = summary
                bucket = "available" if summary["enabled"] else "missing"
                overall["sources"][source_name][bucket] += 1

            theme_summary["companies"].append(
                {
                    "ticker": ticker,
                    "sources": source_status,
                }
            )

        by_theme[theme_name] = theme_summary

    return {
        "overall": overall,
        "by_theme": by_theme,
    }


def build_company_evidence(
    ticker: str,
    ticker_cache: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    cache_key = ticker.upper().strip()
    if ticker_cache is not None and cache_key in ticker_cache:
        return copy.deepcopy(ticker_cache[cache_key])

    profile = get_company_profile(cache_key)
    company_name = profile.get("company_name", cache_key)

    try:
        market_snapshot = get_market_snapshot(cache_key)
    except Exception as e:
        print(f"[WARN] market_snapshot missing for {cache_key}: {e}")
        market_snapshot = {
            "source_name": "market_snapshot",
            "enabled": False,
            "error": str(e),
            "ticker": cache_key,
        }

    try:
        company_news = get_company_news(cache_key, days_back=14, limit=4)
    except Exception as e:
        print(f"[WARN] company_news missing for {cache_key}: {e}")
        company_news = {
            "source_name": "company_news",
            "enabled": False,
            "error": str(e),
            "ticker": cache_key,
            "articles": [],
        }

    try:
        recent_filings = collect_recent_primary_filings(cache_key)
    except Exception as e:
        print(f"[WARN] recent_filings missing for {cache_key}: {e}")
        recent_filings = {
            "enabled": False,
            "error": str(e),
            "ticker": cache_key,
            "recent_10k_10q_8k": [],
        }

    try:
        filing_analysis = collect_filing_analysis(cache_key)
    except Exception as e:
        print(f"[WARN] filing_analysis missing for {cache_key}: {e}")
        filing_analysis = {
            "enabled": False,
            "error": str(e),
            "ticker": cache_key,
            "filing_analysis": {},
        }

    try:
        structured_fundamentals = collect_structured_fundamentals(cache_key)
    except Exception as e:
        print(f"[WARN] structured_fundamentals missing for {cache_key}: {e}")
        structured_fundamentals = {
            "enabled": False,
            "error": str(e),
            "ticker": cache_key,
        }

    try:
        ir_and_transcript_links = get_ir_and_transcript_links(company_name, cache_key)
    except Exception as e:
        print(f"[WARN] ir_and_transcript_links missing for {cache_key}: {e}")
        ir_and_transcript_links = {
            "source_name": "ir_and_transcript_links",
            "enabled": False,
            "error": str(e),
            "ticker": cache_key,
            "results": [],
        }

    company_evidence = {
        "ticker": cache_key,
        "company_profile": profile,
        "market_snapshot": market_snapshot,
        "company_news": company_news,
        "recent_filings": recent_filings,
        "filing_analysis": filing_analysis,
        "structured_fundamentals": structured_fundamentals,
        "ir_and_transcript_links": ir_and_transcript_links,
    }

    if ticker_cache is not None:
        ticker_cache[cache_key] = copy.deepcopy(company_evidence)

    return company_evidence


def build_evidence_pack(
    universe_data: dict[str, Any],
    ticker_cache: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    theme_ticker_map = universe_data.get("theme_ticker_map", {})
    evidence_by_theme: dict[str, list[dict[str, Any]]] = {}

    for theme_name, tickers in theme_ticker_map.items():
        company_evidence_list: list[dict[str, Any]] = []

        for ticker in tickers:
            company_evidence_list.append(build_company_evidence(ticker, ticker_cache=ticker_cache))

        evidence_by_theme[theme_name] = company_evidence_list

    return {
        "themes": universe_data.get("themes", []),
        "theme_ticker_map": theme_ticker_map,
        "evidence_by_theme": evidence_by_theme,
        "data_availability": _build_data_availability_summary(evidence_by_theme),
    }


def filter_evidence_pack_by_sectors(
    evidence_pack: dict[str, Any],
    chosen_sectors: list[dict[str, Any]],
) -> dict[str, Any]:
    chosen_names = [
        sector.get("name", "").strip()
        for sector in chosen_sectors
        if isinstance(sector, dict) and sector.get("name", "").strip()
    ]

    filtered_theme_map = {
        theme_name: evidence_pack.get("theme_ticker_map", {}).get(theme_name, [])
        for theme_name in chosen_names
    }
    filtered_evidence_by_theme = {
        theme_name: copy.deepcopy(evidence_pack.get("evidence_by_theme", {}).get(theme_name, []))
        for theme_name in chosen_names
    }

    return {
        "themes": copy.deepcopy(chosen_sectors),
        "theme_ticker_map": filtered_theme_map,
        "evidence_by_theme": filtered_evidence_by_theme,
        "data_availability": _build_data_availability_summary(filtered_evidence_by_theme),
    }
