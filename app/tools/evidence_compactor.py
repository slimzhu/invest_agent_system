from typing import Any


def compact_company_evidence(company_evidence: dict[str, Any]) -> dict[str, Any]:
    ticker = company_evidence.get("ticker", "")

    profile = company_evidence.get("company_profile", {})
    market = company_evidence.get("market_snapshot", {})
    news = company_evidence.get("company_news", {})
    filings = company_evidence.get("recent_filings", {})
    fundamentals = company_evidence.get("structured_fundamentals", {})
    filing_analysis = company_evidence.get("filing_analysis", {})
    ir_links = company_evidence.get("ir_and_transcript_links", {})

    # ---- news: 兼容 dict / list / None ----
    if isinstance(news, list):
        news_items = news[:2]
    elif isinstance(news, dict):
        news_items = news.get("articles", [])[:2]
    else:
        news_items = []

    compact_news = []
    for item in news_items:
        if not isinstance(item, dict):
            continue
        compact_news.append(
            {
                "headline": item.get("headline", "") or item.get("title", ""),
                "summary": item.get("summary", ""),
                "source": item.get("source", ""),
                "datetime": item.get("datetime", ""),
            }
        )

    # ---- filings: 兼容 dict / list / None ----
    if isinstance(filings, list):
        filing_items = filings[:3]
    elif isinstance(filings, dict):
        filing_items = filings.get("recent_10k_10q_8k", [])[:3]
    else:
        filing_items = []

    compact_filings = []
    for item in filing_items:
        if not isinstance(item, dict):
            continue
        compact_filings.append(
            {
                "form": item.get("form", ""),
                "filing_date": item.get("filing_date", ""),
                "description": item.get("description", ""),
                "filing_url": item.get("filing_url", ""),
            }
        )

    compact_filing_analysis = {}
    if isinstance(filing_analysis, dict):
        analysis = filing_analysis.get("filing_analysis", {})
        if isinstance(analysis, dict):
            compact_filing_analysis = {
                "form": analysis.get("form", ""),
                "filing_date": analysis.get("filing_date", ""),
                "filing_url": analysis.get("filing_url", ""),
                "mda_excerpt": analysis.get("mda_excerpt", ""),
                "segment_or_business_excerpt": analysis.get("segment_or_business_excerpt", ""),
            }

    compact_ir_links = []
    if isinstance(ir_links, dict):
        for result in ir_links.get("results", [])[:3]:
            if not isinstance(result, dict):
                continue
            query = result.get("query", "")
            entries = result.get("results", [])
            for entry in entries[:2]:
                if not isinstance(entry, dict):
                    continue
                compact_ir_links.append(
                    {
                        "query": query,
                        "title": entry.get("title", ""),
                        "description": entry.get("description", ""),
                        "url": entry.get("url", ""),
                    }
                )
        compact_ir_links = compact_ir_links[:4]

    # ---- fundamentals: 兼容缺失 ----
    basic_financials = {}
    quote = {}
    sec_facts = {}

    if isinstance(fundamentals, dict):
        basic_financials = fundamentals.get("basic_financials", {}).get("metric", {})
        quote = fundamentals.get("quote", {}).get("quote", {})
        sec_facts = fundamentals.get("sec_facts_summary", {}).get("key_facts", {})

    compact_fundamentals = {
        "market_cap": basic_financials.get("marketCapitalization"),
        "pe_ttm": basic_financials.get("peTTM"),
        "pb": basic_financials.get("pbAnnual"),
        "ps_ttm": basic_financials.get("psTTM"),
        "roe_ttm": basic_financials.get("roeTTM"),
        "gross_margin_ttm": basic_financials.get("grossMarginTTM"),
        "operating_margin_ttm": basic_financials.get("operatingMarginTTM"),
        "52w_high": basic_financials.get("52WeekHigh"),
        "52w_low": basic_financials.get("52WeekLow"),
        "current_price": quote.get("c"),
        "day_change_pct": quote.get("dp"),
        "Revenue": sec_facts.get("Revenue", {}),
        "NetIncomeLoss": sec_facts.get("NetIncomeLoss", {}),
        "OperatingCashFlow": sec_facts.get("OperatingCashFlow", {}),
        "Capex": sec_facts.get("Capex", {}),
        "GrossProfit": sec_facts.get("GrossProfit", {}),
    }

    # ---- profile: 兼容缺失 ----
    if not isinstance(profile, dict):
        profile = {}

    compact_profile = {
        "company_name": profile.get("company_name", ""),
        "sector": profile.get("sector", ""),
        "industry": profile.get("industry", ""),
        "business_summary": profile.get("business_summary", ""),
        "market_position": profile.get("market_position", ""),
        "profitability_notes": profile.get("profitability_notes", ""),
        "balance_sheet_notes": profile.get("balance_sheet_notes", ""),
        "valuation_notes": profile.get("valuation_notes", ""),
        "key_risks": profile.get("key_risks", [])[:3] if isinstance(profile.get("key_risks", []), list) else [],
        "as_of_utc": profile.get("as_of_utc", ""),
    }

    # ---- market: 兼容缺失 ----
    if not isinstance(market, dict):
        market = {}

    compact_market = {
        "price_trend": market.get("price_trend", ""),
        "relative_strength": market.get("relative_strength", ""),
        "volatility": market.get("volatility", ""),
        "current_price": market.get("current_price"),
        "day_change_pct": market.get("day_change_pct"),
        "52w_high": market.get("52w_high"),
        "52w_low": market.get("52w_low"),
        "as_of_utc": market.get("as_of_utc", ""),
    }

    return {
        "ticker": ticker,
        "analysis_ready": company_evidence.get("analysis_ready", False),
        "analysis_readiness_reasons": company_evidence.get("analysis_readiness_reasons", []),
        "company_profile": compact_profile,
        "market_snapshot": compact_market,
        "recent_news": compact_news,
        "recent_filings": compact_filings,
        "filing_analysis_summary": compact_filing_analysis,
        "ir_materials": compact_ir_links,
        "fundamentals_summary": compact_fundamentals,
    }


def compact_evidence_pack(
    evidence_pack: dict[str, Any],
    max_companies_per_theme: int = 4,
) -> dict[str, Any]:
    compacted = {
        "themes": evidence_pack.get("themes", []),
        "theme_ticker_map": evidence_pack.get("theme_ticker_map", {}),
        "evidence_by_theme": {},
        "data_availability": evidence_pack.get("data_availability", {}),
    }

    for theme_name, companies in evidence_pack.get("evidence_by_theme", {}).items():
        if not isinstance(companies, list):
            compacted["evidence_by_theme"][theme_name] = []
            continue

        compacted["evidence_by_theme"][theme_name] = [
            compact_company_evidence(company)
            for company in companies[:max_companies_per_theme]
            if isinstance(company, dict)
        ]

    return compacted
