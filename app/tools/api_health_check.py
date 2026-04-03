from __future__ import annotations

from app.sources.research_sources import (
    get_brave_search_results,
    get_finnhub_market_news,
)
from app.sources.news_sources import get_company_news
from app.sources.filings_sources import (
    get_sec_company_facts,
    get_sec_company_submissions,
)
from app.tools.fundamentals_collector import (
    get_finnhub_basic_financials,
    get_finnhub_quote,
)


def print_section(title: str) -> None:
    print("\n" + "=" * 20, title, "=" * 20)


def api_health_check() -> None:
    print_section("ENV CHECK")

    import os
    print("FINNHUB_API_KEY set:", bool(os.getenv("FINNHUB_API_KEY")))
    print("BRAVE_API_KEY set:", bool(os.getenv("BRAVE_API_KEY")))
    print("SEC_USER_AGENT set:", bool(os.getenv("SEC_USER_AGENT")))
    print("HTTP_PROXY:", os.getenv("HTTP_PROXY"))
    print("HTTPS_PROXY:", os.getenv("HTTPS_PROXY"))

    print_section("FINNHUB MARKET NEWS")
    market_news = get_finnhub_market_news(category="general", limit=2)
    print("enabled:", market_news.get("enabled"))
    print("source_name:", market_news.get("source_name"))
    print("articles_count:", len(market_news.get("articles", [])))
    print("error:", market_news.get("error"))

    print_section("FINNHUB COMPANY NEWS")
    company_news = get_company_news("MU", days_back=7, limit=2)
    if isinstance(company_news, dict):
        print("enabled:", company_news.get("enabled"))
        print("articles_count:", len(company_news.get("articles", [])))
        print("error:", company_news.get("error"))
    else:
        print("returned non-dict:", type(company_news))

    print_section("FINNHUB QUOTE")
    quote = get_finnhub_quote("MU")
    print("enabled:", quote.get("enabled"))
    print("quote:", quote.get("quote"))
    print("error:", quote.get("error"))

    print_section("FINNHUB BASIC FINANCIALS")
    fin = get_finnhub_basic_financials("MU")
    print("enabled:", fin.get("enabled"))
    print("has_metric:", bool(fin.get("metric")))
    print("error:", fin.get("error"))

    print_section("BRAVE SEARCH")
    brave = get_brave_search_results("memory cycle investing thesis", count=2)
    print("enabled:", brave.get("enabled"))
    print("results_count:", len(brave.get("results", [])))
    print("reason/error:", brave.get("reason") or brave.get("error"))

    print_section("SEC SUBMISSIONS")
    sec_sub = get_sec_company_submissions("723125")  # MU
    print("enabled:", sec_sub.get("enabled"))
    print("company_name:", sec_sub.get("company_name"))
    print("has_filings:", bool(sec_sub.get("filings")))
    print("error:", sec_sub.get("error"))

    print_section("SEC COMPANY FACTS")
    sec_facts = get_sec_company_facts("723125")  # MU
    print("enabled:", sec_facts.get("enabled"))
    print("entity_name:", sec_facts.get("entity_name"))
    print("has_facts:", bool(sec_facts.get("facts")))
    print("error:", sec_facts.get("error"))