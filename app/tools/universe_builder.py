from typing import Any

from app.sources.universe_sources import build_theme_ticker_map


def _dedupe_sectors(sectors: list[dict[str, Any]]) -> list[dict[str, Any]]:
    deduped: list[dict[str, Any]] = []
    seen = set()

    for sector in sectors:
        if not isinstance(sector, dict):
            continue
        name = sector.get("name", "").strip()
        if not name or name in seen:
            continue
        seen.add(name)
        deduped.append(sector)

    return deduped


def build_stock_universe_from_sectors(sectors: list[dict[str, Any]]) -> dict[str, Any]:
    deduped_sectors = _dedupe_sectors(sectors)
    theme_ticker_map = build_theme_ticker_map(deduped_sectors)

    all_tickers: list[str] = []
    seen = set()

    for _, tickers in theme_ticker_map.items():
        for ticker in tickers:
            if ticker not in seen:
                seen.add(ticker)
                all_tickers.append(ticker)

    return {
        "themes": deduped_sectors,
        "theme_ticker_map": theme_ticker_map,
        "all_candidate_tickers": all_tickers,
    }


def build_stock_universe_from_research(research_data: dict[str, Any]) -> dict[str, Any]:
    final_sectors = research_data.get("final_sectors", [])
    return build_stock_universe_from_sectors(final_sectors)


def build_stock_universe_for_trader_pool(research_data: dict[str, Any]) -> dict[str, Any]:
    candidate_sectors = research_data.get("candidate_sectors", [])
    final_sectors = research_data.get("final_sectors", [])
    return build_stock_universe_from_sectors(candidate_sectors + final_sectors)
