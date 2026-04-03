from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.config import settings
from app.utils.http_utils import get_json_with_resilience


def _safe_get_json(url: str, params: dict[str, Any]) -> dict[str, Any]:
    data = get_json_with_resilience(
        url,
        params=params,
        timeout=(8, 20),
        retries=2,
        use_proxy=True,
    )
    if isinstance(data, dict) and data.get("_error"):
        return {}
    return data if isinstance(data, dict) else {}


def _price_trend(current: float | None, week_low: float | None, week_high: float | None) -> str:
    if current is None or week_low is None or week_high is None or week_high <= week_low:
        return "unavailable"

    position = (current - week_low) / (week_high - week_low)
    if position >= 0.8:
        return "strong_uptrend"
    if position >= 0.6:
        return "uptrend"
    if position >= 0.4:
        return "range_bound"
    if position >= 0.2:
        return "downtrend"
    return "weak_downtrend"


def _relative_strength(current: float | None, week_low: float | None, week_high: float | None) -> str:
    if current is None or week_low is None or week_high is None or week_high <= week_low:
        return "unavailable"

    position = (current - week_low) / (week_high - week_low)
    if position >= 0.75:
        return "high"
    if position >= 0.5:
        return "medium_high"
    if position >= 0.25:
        return "medium"
    return "low"


def _volatility(beta: float | None, day_change_pct: float | None) -> str:
    if beta is None and day_change_pct is None:
        return "unavailable"

    score = max(abs(beta or 0), abs(day_change_pct or 0) / 2)
    if score >= 2:
        return "high"
    if score >= 1:
        return "medium"
    return "low"


def get_market_snapshot(ticker: str) -> dict[str, Any]:
    ticker = ticker.upper().strip()

    if not settings.FINNHUB_API_KEY:
        return {
            "source_name": "market_snapshot",
            "enabled": False,
            "ticker": ticker,
            "error": "FINNHUB_API_KEY missing",
        }

    quote = _safe_get_json(
        "https://finnhub.io/api/v1/quote",
        {"symbol": ticker, "token": settings.FINNHUB_API_KEY},
    )
    metrics = _safe_get_json(
        "https://finnhub.io/api/v1/stock/metric",
        {"symbol": ticker, "metric": "all", "token": settings.FINNHUB_API_KEY},
    )

    metric_block = metrics.get("metric", {})
    current_price = quote.get("c")
    previous_close = quote.get("pc")
    week_high = metric_block.get("52WeekHigh")
    week_low = metric_block.get("52WeekLow")

    try:
        day_change_pct = (
            ((float(current_price) - float(previous_close)) / float(previous_close)) * 100
            if current_price not in (None, "") and previous_close not in (None, "", 0)
            else None
        )
    except (TypeError, ValueError, ZeroDivisionError):
        day_change_pct = None

    beta = metric_block.get("beta")
    enabled = bool(quote or metric_block)

    return {
        "source_name": "market_snapshot",
        "enabled": enabled,
        "ticker": ticker,
        "current_price": current_price,
        "previous_close": previous_close,
        "day_change_pct": day_change_pct,
        "day_high": quote.get("h"),
        "day_low": quote.get("l"),
        "open": quote.get("o"),
        "52w_high": week_high,
        "52w_low": week_low,
        "beta": beta,
        "price_trend": _price_trend(current_price, week_low, week_high),
        "relative_strength": _relative_strength(current_price, week_low, week_high),
        "volatility": _volatility(beta, day_change_pct),
        "as_of_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "error": None if enabled else "Quote and metric endpoints both returned empty payloads",
    }
