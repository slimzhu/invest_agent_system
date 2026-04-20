from __future__ import annotations

from typing import Any

from app.sources.filings_sources import (
    extract_recent_filings,
    fetch_filing_text,
    get_sec_company_submissions,
)
from app.tools.filing_parser import (
    clean_filing_text,
    compact_section,
    extract_mda_section,
    extract_segment_or_business_section,
)


TICKER_TO_CIK = {
    "NVDA": "1045810",
    "AVGO": "1730168",
    "ANET": "1596532",
    "MU": "723125",
    "LLY": "59478",
    "XOM": "34088",
    "CAT": "18230",
    "ETN": "1551182",
    "AMAT": "6951",
    "LRCX": "707549",
    "KLAC": "319201",
    "WDC": "106040",
    "VRT": "1674101",
    "PWR": "1050915",
    "HUBB": "48898",
    "NVT": "1688568",
    "GEV": "1996810",
    "CIEN": "936395",
    "LITE": "1633978",
    "COHR": "21510",
    "TSM": "1046179",
    "ASML": "937966",
    "ARM": "1973239",
    "GFS": "1709048",
    "UMC": "1033767",
    "AMKR": "1047127",
}


def get_cik_for_ticker(ticker: str) -> str:
    return TICKER_TO_CIK.get(ticker.upper().strip(), "")


def collect_recent_primary_filings(ticker: str) -> dict[str, Any]:
    cik = get_cik_for_ticker(ticker)
    if not cik:
        return {
            "ticker": ticker.upper().strip(),
            "enabled": False,
            "reason": "CIK mapping not found",
            "recent_10k_10q_8k": [],
        }

    submissions = get_sec_company_submissions(cik)
    if not submissions.get("enabled"):
        return {
            "ticker": ticker.upper().strip(),
            "enabled": False,
            "reason": submissions.get("error", "SEC submissions unavailable"),
            "recent_10k_10q_8k": [],
        }

    recent_filings = extract_recent_filings(
        submissions,
        forms_filter=["10-K", "10-Q", "8-K", "DEF 14A", "20-F", "6-K", "40-F"],
        max_items=10,
    )

    return {
        "ticker": ticker.upper().strip(),
        "enabled": True,
        "company_name": submissions.get("company_name", ""),
        "cik": cik,
        "recent_10k_10q_8k": recent_filings,
    }


def collect_filing_analysis(ticker: str) -> dict[str, Any]:
    filings_data = collect_recent_primary_filings(ticker)
    filings = filings_data.get("recent_10k_10q_8k", [])

    primary_filing = None
    for item in filings:
        if item.get("form") in {"10-K", "10-Q", "8-K", "20-F", "6-K", "40-F"} and item.get("filing_url"):
            primary_filing = item
            break

    if not primary_filing:
        return {
            "ticker": ticker.upper().strip(),
            "enabled": False,
            "reason": "No analyzable filing found",
            "filing_analysis": {},
        }

    raw_text = fetch_filing_text(primary_filing["filing_url"])
    if raw_text.startswith("__REQUEST_FAILED__"):
        return {
            "ticker": ticker.upper().strip(),
            "enabled": False,
            "reason": raw_text,
            "filing_analysis": {},
        }

    cleaned = clean_filing_text(raw_text)
    form = primary_filing.get("form", "")

    mda = compact_section(extract_mda_section(cleaned, form), max_chars=2200)
    segment_or_business = compact_section(
        extract_segment_or_business_section(cleaned, form),
        max_chars=1800,
    )

    return {
        "ticker": ticker.upper().strip(),
        "enabled": True,
        "filing_analysis": {
            "form": form,
            "filing_date": primary_filing.get("filing_date", ""),
            "filing_url": primary_filing.get("filing_url", ""),
            "mda_excerpt": mda,
            "segment_or_business_excerpt": segment_or_business,
        },
    }
