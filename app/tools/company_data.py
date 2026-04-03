from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.config import settings
from app.sources.filings_sources import (
    extract_key_company_facts,
    get_sec_company_facts,
    get_sec_company_submissions,
)
from app.tools.filings_collector import get_cik_for_ticker
from app.utils.http_utils import get_json_with_resilience


def _get_finnhub_company_profile(symbol: str) -> dict[str, Any]:
    if not settings.FINNHUB_API_KEY:
        return {
            "enabled": False,
            "symbol": symbol,
            "profile": {},
            "error": "FINNHUB_API_KEY missing",
        }

    url = "https://finnhub.io/api/v1/stock/profile2"
    params = {
        "symbol": symbol.upper().strip(),
        "token": settings.FINNHUB_API_KEY,
    }

    data = get_json_with_resilience(
        url,
        params=params,
        timeout=(10, 30),
        retries=2,
        use_proxy=True,
    )

    if isinstance(data, dict) and data.get("_error"):
        return {
            "enabled": False,
            "symbol": symbol.upper().strip(),
            "profile": {},
            "error": data["_error"],
        }

    if not isinstance(data, dict):
        return {
            "enabled": False,
            "symbol": symbol.upper().strip(),
            "profile": {},
            "error": "Unexpected Finnhub profile payload",
        }

    return {
        "enabled": bool(data.get("name") or data.get("finnhubIndustry")),
        "symbol": symbol.upper().strip(),
        "profile": data,
        "error": None if data else "Empty Finnhub profile response",
    }


def _fmt_metric(value: Any, suffix: str = "") -> str:
    if value in (None, "", "None"):
        return ""

    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)

    if suffix == "%":
        return f"{number:.1f}%"
    if abs(number) >= 1_000:
        return f"{number:,.0f}{suffix}"
    if abs(number) >= 10:
        return f"{number:.1f}{suffix}"
    return f"{number:.2f}{suffix}"


def _fmt_money_short(value: Any) -> str:
    if value in (None, "", "None"):
        return ""

    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)

    absolute = abs(number)
    if absolute >= 1_000_000_000:
        return f"${number / 1_000_000_000:.2f}B"
    if absolute >= 1_000_000:
        return f"${number / 1_000_000:.2f}M"
    if absolute >= 1_000:
        return f"${number / 1_000:.2f}K"
    return f"${number:,.0f}"


def _latest_fact_text(label: str, fact: dict[str, Any]) -> str:
    if not isinstance(fact, dict) or not fact:
        return ""

    value = fact.get("val")
    if value in (None, ""):
        return ""

    period = " ".join(
        str(part).strip()
        for part in [fact.get("fy"), fact.get("fp")]
        if part not in (None, "")
    ).strip()
    period_suffix = f" ({period})" if period else ""
    return f"{label}: {_fmt_money_short(value)}{period_suffix}"


def _build_business_summary(
    company_name: str,
    finnhub_profile: dict[str, Any],
    submissions_data: dict[str, Any],
) -> str:
    descriptors: list[str] = []

    industry = str(finnhub_profile.get("finnhubIndustry", "")).strip()
    sic_description = str(submissions_data.get("sic_description", "")).strip()
    exchange = str(finnhub_profile.get("exchange", "")).strip()
    country = str(finnhub_profile.get("country", "")).strip()

    if industry:
        descriptors.append(f"Finnhub industry: {industry}.")
    if sic_description and sic_description != industry:
        descriptors.append(f"SEC SIC description: {sic_description}.")
    if exchange or country:
        exchange_line = ", ".join(part for part in [exchange, country] if part)
        descriptors.append(f"Listed market metadata: {exchange_line}.")

    if not descriptors:
        return ""

    prefix = f"{company_name} live profile summary. " if company_name else ""
    return prefix + " ".join(descriptors)


def _build_market_position(
    finnhub_profile: dict[str, Any],
    quote_data: dict[str, Any],
) -> str:
    points: list[str] = []

    market_cap = finnhub_profile.get("marketCapitalization")
    if market_cap not in (None, ""):
        points.append(f"Finnhub market capitalization: {_fmt_money_short(float(market_cap) * 1_000_000)}.")

    current_price = quote_data.get("c")
    if current_price not in (None, ""):
        points.append(f"Current price: {_fmt_metric(current_price)}.")

    week_high = quote_data.get("h")
    week_low = quote_data.get("l")
    if week_high not in (None, "") and week_low not in (None, ""):
        points.append(f"Session range: {_fmt_metric(week_low)} to {_fmt_metric(week_high)}.")

    return " ".join(points)


def _build_revenue_characteristics(
    key_facts: dict[str, Any],
) -> str:
    revenue_text = _latest_fact_text("Latest SEC revenue fact", key_facts.get("Revenue", {}))
    gross_profit_text = _latest_fact_text("Latest SEC gross profit fact", key_facts.get("GrossProfit", {}))
    return " ".join(part for part in [revenue_text, gross_profit_text] if part)


def _build_profitability_notes(
    basic_metrics: dict[str, Any],
    key_facts: dict[str, Any],
) -> str:
    points: list[str] = []

    gross_margin = basic_metrics.get("grossMarginTTM")
    if gross_margin not in (None, ""):
        points.append(f"Gross margin TTM: {_fmt_metric(gross_margin, '%')}.")

    operating_margin = basic_metrics.get("operatingMarginTTM")
    if operating_margin not in (None, ""):
        points.append(f"Operating margin TTM: {_fmt_metric(operating_margin, '%')}.")

    roe = basic_metrics.get("roeTTM")
    if roe not in (None, ""):
        points.append(f"ROE TTM: {_fmt_metric(roe, '%')}.")

    net_income_text = _latest_fact_text("Latest SEC net income fact", key_facts.get("NetIncomeLoss", {}))
    if net_income_text:
        points.append(net_income_text + ".")

    return " ".join(points)


def _build_balance_sheet_notes(
    key_facts: dict[str, Any],
) -> str:
    points: list[str] = []

    assets_text = _latest_fact_text("Latest SEC assets fact", key_facts.get("Assets", {}))
    if assets_text:
        points.append(assets_text + ".")

    ocf_text = _latest_fact_text("Latest SEC operating cash flow fact", key_facts.get("OperatingCashFlow", {}))
    if ocf_text:
        points.append(ocf_text + ".")

    capex_text = _latest_fact_text("Latest SEC capex fact", key_facts.get("Capex", {}))
    if capex_text:
        points.append(capex_text + ".")

    return " ".join(points)


def _build_valuation_notes(
    basic_metrics: dict[str, Any],
    quote_data: dict[str, Any],
) -> str:
    points: list[str] = []

    pe = basic_metrics.get("peTTM")
    pb = basic_metrics.get("pbAnnual")
    ps = basic_metrics.get("psTTM")
    current_price = quote_data.get("c")

    if current_price not in (None, ""):
        points.append(f"Current price: {_fmt_metric(current_price)}.")
    if pe not in (None, ""):
        points.append(f"PE TTM: {_fmt_metric(pe)}.")
    if pb not in (None, ""):
        points.append(f"PB: {_fmt_metric(pb)}.")
    if ps not in (None, ""):
        points.append(f"PS TTM: {_fmt_metric(ps)}.")

    return " ".join(points)


def _build_key_risks(
    submissions_data: dict[str, Any],
    finnhub_profile: dict[str, Any],
    key_facts: dict[str, Any],
) -> list[str]:
    risks: list[str] = []

    sic_description = str(submissions_data.get("sic_description", "")).strip()
    if sic_description:
        risks.append(f"Primary SEC industry exposure: {sic_description}.")

    revenue_text = _latest_fact_text("Latest SEC revenue fact", key_facts.get("Revenue", {}))
    if revenue_text:
        risks.append(f"Revenue concentration and cyclicality should be checked against latest filings; {revenue_text}.")

    market_cap = finnhub_profile.get("marketCapitalization")
    if market_cap not in (None, ""):
        risks.append(
            f"Market-cap sensitivity should be evaluated against liquidity and valuation moves; Finnhub market cap: "
            f"{_fmt_money_short(float(market_cap) * 1_000_000)}."
        )

    return risks[:3]


def get_company_profile(ticker: str) -> dict[str, Any]:
    ticker = ticker.upper().strip()
    cik = get_cik_for_ticker(ticker)

    finnhub_company = _get_finnhub_company_profile(ticker)
    finnhub_profile = finnhub_company.get("profile", {})

    submissions_data: dict[str, Any] = {}
    company_facts_data: dict[str, Any] = {}
    key_facts: dict[str, Any] = {}

    if cik:
        submissions_data = get_sec_company_submissions(cik)
        company_facts_data = get_sec_company_facts(cik)
        key_facts = extract_key_company_facts(company_facts_data).get("key_facts", {})

    basic_metrics: dict[str, Any] = {}
    quote_data: dict[str, Any] = {}

    if settings.FINNHUB_API_KEY:
        profile_metrics = get_json_with_resilience(
            "https://finnhub.io/api/v1/stock/metric",
            params={
                "symbol": ticker,
                "metric": "all",
                "token": settings.FINNHUB_API_KEY,
            },
            timeout=(10, 30),
            retries=2,
            use_proxy=True,
        )
        if isinstance(profile_metrics, dict) and not profile_metrics.get("_error"):
            basic_metrics = profile_metrics.get("metric", {})

        quote_payload = get_json_with_resilience(
            "https://finnhub.io/api/v1/quote",
            params={
                "symbol": ticker,
                "token": settings.FINNHUB_API_KEY,
            },
            timeout=(10, 30),
            retries=2,
            use_proxy=True,
        )
        if isinstance(quote_payload, dict) and not quote_payload.get("_error"):
            quote_data = quote_payload

    company_name = (
        str(finnhub_profile.get("name", "")).strip()
        or str(submissions_data.get("company_name", "")).strip()
        or str(company_facts_data.get("entity_name", "")).strip()
    )
    industry = str(finnhub_profile.get("finnhubIndustry", "")).strip()
    sec_sic_description = str(submissions_data.get("sic_description", "")).strip()
    sector = industry or sec_sic_description

    source_errors = [
        finnhub_company.get("error"),
        submissions_data.get("error"),
        company_facts_data.get("error"),
    ]
    source_errors = [error for error in source_errors if error]

    enabled = bool(company_name or industry or sec_sic_description or key_facts)

    if not enabled:
        return {
            "ticker": ticker,
            "enabled": False,
            "source": "live",
            "company_name": "",
            "sector": "",
            "industry": "",
            "business_summary": "",
            "market_position": "",
            "revenue_characteristics": "",
            "profitability_notes": "",
            "balance_sheet_notes": "",
            "valuation_notes": "",
            "key_risks": [],
            "cik": cik,
            "as_of_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "error": "; ".join(source_errors) or "No live company profile data available from configured sources.",
        }

    return {
        "ticker": ticker,
        "enabled": True,
        "source": "live",
        "company_name": company_name,
        "sector": sector,
        "industry": industry or sec_sic_description,
        "business_summary": _build_business_summary(company_name, finnhub_profile, submissions_data),
        "market_position": _build_market_position(finnhub_profile, quote_data),
        "revenue_characteristics": _build_revenue_characteristics(key_facts),
        "profitability_notes": _build_profitability_notes(basic_metrics, key_facts),
        "balance_sheet_notes": _build_balance_sheet_notes(key_facts),
        "valuation_notes": _build_valuation_notes(basic_metrics, quote_data),
        "key_risks": _build_key_risks(submissions_data, finnhub_profile, key_facts),
        "cik": cik,
        "as_of_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "sec_company_name": submissions_data.get("company_name", ""),
        "sec_sic_description": sec_sic_description,
        "error": None if not source_errors else "; ".join(source_errors),
    }
