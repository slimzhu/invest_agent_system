from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from app.config import settings
from app.utils.http_utils import get_json_with_resilience


def _utc_date_str(days_ago: int = 7) -> str:
    dt = datetime.now(timezone.utc) - timedelta(days=days_ago)
    return dt.strftime("%Y-%m-%d")

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

def get_finnhub_market_news(category: str = "general", limit: int = 8) -> dict[str, Any]:
    if not settings.FINNHUB_API_KEY or not settings.RESEARCH_SOURCE_ENABLE_FINNHUB:
        return {
            "source_name": "finnhub_market_news",
            "enabled": False,
            "reason": "FINNHUB disabled or key missing",
            "articles": [],
        }

    url = "https://finnhub.io/api/v1/news"
    params = {"category": category, "token": settings.FINNHUB_API_KEY}
    data = _safe_get_json(url, params=params)
    articles = data[:limit] if isinstance(data, list) else []
    enabled = isinstance(data, list)

    normalized = []
    for item in articles:
        normalized.append(
            {
                "headline": item.get("headline", ""),
                "summary": item.get("summary", ""),
                "source": item.get("source", ""),
                "url": item.get("url", ""),
                "datetime": item.get("datetime", ""),
                "related": item.get("related", ""),
            }
        )

    return {
        "source_name": "finnhub_market_news",
        "enabled": enabled,
        "category": category,
        "articles": normalized,
        "error": None if enabled else "API failed or empty response",
    }


def get_finnhub_company_news(symbol: str, days_back: int = 21, limit: int = 6) -> dict[str, Any]:
    if not settings.FINNHUB_API_KEY or not settings.RESEARCH_SOURCE_ENABLE_FINNHUB:
        return {
            "source_name": "finnhub_company_news",
            "enabled": False,
            "reason": "FINNHUB disabled or key missing",
            "symbol": symbol,
            "articles": [],
        }

    url = "https://finnhub.io/api/v1/company-news"
    params = {
        "symbol": symbol.upper().strip(),
        "from": _utc_date_str(days_back),
        "to": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "token": settings.FINNHUB_API_KEY,
    }
    data = _safe_get_json(url, params=params)
    articles = data[:limit] if isinstance(data, list) else []
    enabled = isinstance(data, list)

    normalized = []
    for item in articles:
        normalized.append(
            {
                "headline": item.get("headline", ""),
                "summary": item.get("summary", ""),
                "source": item.get("source", ""),
                "url": item.get("url", ""),
                "datetime": item.get("datetime", ""),
                "related": item.get("related", ""),
            }
        )

    return {
        "source_name": "finnhub_company_news",
        "enabled": enabled,
        "symbol": symbol.upper().strip(),
        "articles": normalized,
        "error": None if enabled else "API failed or empty response",
    }


def get_brave_search_results(query: str, count: int = 5) -> dict[str, Any]:
    if not settings.BRAVE_API_KEY or not settings.RESEARCH_SOURCE_ENABLE_BRAVE:
        return {
            "source_name": "brave_search",
            "enabled": False,
            "reason": "BRAVE disabled or key missing",
            "query": query,
            "results": [],
        }

    url = "https://api.search.brave.com/res/v1/web/search"
    headers = {
        "Accept": "application/json",
        "Accept-Encoding": "gzip",
        "X-Subscription-Token": settings.BRAVE_API_KEY,
        "Cache-Control": "no-cache",
    }
    params = {
        "q": query,
        "count": count,
    }

    data = _safe_get_json(url, params=params, headers=headers)
    if not isinstance(data, dict):
        data = {}
    web_results = data.get("web", {}).get("results", [])
    enabled = bool(web_results)

    normalized = []
    for item in web_results:
        normalized.append(
            {
                "title": item.get("title", ""),
                "description": item.get("description", ""),
                "url": item.get("url", ""),
            }
        )

    return {
        "source_name": "brave_search",
        "enabled": enabled,
        "query": query,
        "results": normalized,
        "error": None if enabled else "API failed or empty response",
    }


def get_sec_company_submissions(cik: str) -> dict[str, Any]:
    """
    SEC public data API: submissions/CIK##########.json
    cik must be numeric; function pads to 10 digits.
    """
    if not settings.RESEARCH_SOURCE_ENABLE_SEC:
        return {
            "source_name": "sec_submissions",
            "enabled": False,
            "reason": "SEC source disabled",
            "cik": cik,
            "data": {},
        }

    cik_num = "".join(ch for ch in cik if ch.isdigit()).zfill(10)
    url = f"https://data.sec.gov/submissions/CIK{cik_num}.json"
    headers = {
        "User-Agent": settings.SEC_USER_AGENT,
        "Accept-Encoding": "gzip, deflate",
        "Host": "data.sec.gov",
    }

    data = _safe_get_json(url, headers=headers)
    if not isinstance(data, dict) or not data:
        return {
            "source_name": "sec_submissions",
            "enabled": False,
            "cik": cik_num,
            "company_name": "",
            "ticker": "",
            "sic_description": "",
            "recent_forms": [],
            "error": "API failed or empty response",
        }

    recent = data.get("filings", {}).get("recent", {})
    recent_forms = []
    forms = recent.get("form", [])
    filing_dates = recent.get("filingDate", [])
    accession_numbers = recent.get("accessionNumber", [])

    for i in range(min(8, len(forms))):
        recent_forms.append(
            {
                "form": forms[i] if i < len(forms) else "",
                "filing_date": filing_dates[i] if i < len(filing_dates) else "",
                "accession_number": accession_numbers[i] if i < len(accession_numbers) else "",
            }
        )

    return {
        "source_name": "sec_submissions",
        "enabled": True,
        "cik": cik_num,
        "company_name": data.get("name", ""),
        "ticker": data.get("tickers", [""])[0] if data.get("tickers") else "",
        "sic_description": data.get("sicDescription", ""),
        "recent_forms": recent_forms,
        "error": None,
    }


def get_sec_company_facts(cik: str) -> dict[str, Any]:
    """
    SEC public data API: api/xbrl/companyfacts/CIK##########.json
    """
    if not settings.RESEARCH_SOURCE_ENABLE_SEC:
        return {
            "source_name": "sec_company_facts",
            "enabled": False,
            "reason": "SEC source disabled",
            "cik": cik,
            "facts_summary": {},
        }

    cik_num = "".join(ch for ch in cik if ch.isdigit()).zfill(10)
    url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik_num}.json"
    headers = {
        "User-Agent": settings.SEC_USER_AGENT,
        "Accept-Encoding": "gzip, deflate",
        "Host": "data.sec.gov",
    }

    data = _safe_get_json(url, headers=headers)
    if not isinstance(data, dict) or not data:
        return {
            "source_name": "sec_company_facts",
            "enabled": False,
            "cik": cik_num,
            "entity_name": "",
            "facts_summary": {},
            "error": "API failed or empty response",
        }

    us_gaap = data.get("facts", {}).get("us-gaap", {})

    def _latest_fact(key: str) -> dict[str, Any]:
        fact = us_gaap.get(key, {})
        units = fact.get("units", {})
        latest: dict[str, Any] = {}
        latest_key: tuple[Any, ...] | None = None
        for _, values in units.items():
            if not isinstance(values, list):
                continue
            for item in values:
                if not isinstance(item, dict):
                    continue
                key_tuple = (
                    item.get("fy") or 0,
                    item.get("filed") or "",
                    item.get("end") or "",
                    item.get("frame") or "",
                    item.get("form") or "",
                )
                if latest_key is None or key_tuple > latest_key:
                    latest_key = key_tuple
                    latest = item
        if latest:
            return latest
        return {}

    return {
        "source_name": "sec_company_facts",
        "enabled": True,
        "cik": cik_num,
        "entity_name": data.get("entityName", ""),
        "facts_summary": {
            "Revenue": _latest_fact("Revenues"),
            "NetIncomeLoss": _latest_fact("NetIncomeLoss"),
            "Assets": _latest_fact("Assets"),
        },
        "error": None,
    }
