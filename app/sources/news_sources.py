from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from app.config import settings
from app.utils.http_utils import get_json_with_resilience


def _safe_get_json(url, params=None, headers=None):
    data = get_json_with_resilience(
        url,
        params=params,
        headers=headers,
        timeout=(8, 20),
        retries=2,
        use_proxy=True,
    )
    if isinstance(data, dict) and data.get("_error"):
        print(f"[WARN] News API failed: {data['_error']}")
        return None
    return data


def _utc_date_str(days_ago: int = 14) -> str:
    dt = datetime.now(timezone.utc) - timedelta(days=days_ago)
    return dt.strftime("%Y-%m-%d")


def get_company_news(symbol: str, days_back: int = 14, limit: int = 6) -> dict[str, Any]:
    symbol = symbol.upper().strip()

    # ❗无 key 情况
    if not settings.FINNHUB_API_KEY:
        return {
            "source_name": "company_news",
            "enabled": False,
            "symbol": symbol,
            "articles": [],
            "error": "FINNHUB_API_KEY missing",
        }

    url = "https://finnhub.io/api/v1/company-news"
    params = {
        "symbol": symbol,
        "from": _utc_date_str(days_back),
        "to": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "token": settings.FINNHUB_API_KEY,
    }

    data = _safe_get_json(url, params=params)

    # ❗关键：失败也必须返回 dict
    if not data:
        return {
            "source_name": "company_news",
            "enabled": False,
            "symbol": symbol,
            "articles": [],
            "error": "API failed or empty response",
        }

    # Finnhub 正常返回 list
    if isinstance(data, list):
        articles = data[:limit]
    else:
        articles = []

    normalized = []
    for item in articles:
        if not isinstance(item, dict):
            continue

        normalized.append(
            {
                "headline": item.get("headline", ""),
                "summary": item.get("summary", ""),
                "source": item.get("source", ""),
                "url": item.get("url", ""),
                "datetime": item.get("datetime", ""),
            }
        )

    return {
        "source_name": "company_news",
        "enabled": True,
        "symbol": symbol,
        "articles": normalized,
        "error": None,
    }
