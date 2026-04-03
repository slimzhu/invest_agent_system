from typing import Any


THEME_TO_TICKERS: dict[str, list[str]] = {
    "optical networking": ["ANET", "CIEN", "LITE", "COHR", "AVGO"],
    "ai infrastructure": ["NVDA", "AVGO", "ANET", "AMD", "VRT", "ETN"],
    "memory cycle": ["MU", "WDC", "AMAT", "LRCX", "KLAC"],
    "memory supercycle": ["MU", "WDC", "AMAT", "LRCX", "KLAC"],
    "power grid": ["ETN", "HUBB", "PWR", "VRT", "NVT", "GEV"],
    "data center power": ["ETN", "VRT", "PWR", "HUBB", "NVT", "GEV"],
    "power grid and data center power equipment": ["ETN", "VRT", "PWR", "HUBB", "NVT", "GEV"],
    "power and cooling": ["ETN", "VRT", "PWR", "HUBB", "NVT", "GEV"],
}


def normalize_theme_name(theme_name: str) -> str:
    return theme_name.strip().lower()


def get_theme_seed_tickers(theme_name: str) -> list[str]:
    normalized = normalize_theme_name(theme_name)

    # 1. exact match
    if normalized in THEME_TO_TICKERS:
        return THEME_TO_TICKERS[normalized]

    # 2. substring / alias match
    matched: list[str] = []
    seen = set()

    for key, tickers in THEME_TO_TICKERS.items():
        if key in normalized or normalized in key:
            for ticker in tickers:
                if ticker not in seen:
                    seen.add(ticker)
                    matched.append(ticker)

    if matched:
        return matched

    # 3. keyword fallback
    fallback: list[str] = []
    seen = set()

    keyword_map = {
        "memory": ["MU", "WDC", "AMAT", "LRCX", "KLAC"],
        "optical": ["ANET", "CIEN", "LITE", "COHR", "AVGO"],
        "network": ["ANET", "CIEN", "AVGO"],
        "ai": ["NVDA", "AVGO", "ANET", "AMD", "VRT", "ETN"],
        "power": ["ETN", "VRT", "PWR", "HUBB", "NVT", "GEV"],
        "cooling": ["VRT", "ETN", "PWR"],
        "grid": ["ETN", "HUBB", "PWR", "NVT", "GEV"],
    }

    for keyword, tickers in keyword_map.items():
        if keyword in normalized:
            for ticker in tickers:
                if ticker not in seen:
                    seen.add(ticker)
                    fallback.append(ticker)

    return fallback


def build_theme_ticker_map(final_sectors: list[dict[str, Any]]) -> dict[str, list[str]]:
    theme_map: dict[str, list[str]] = {}

    for sector in final_sectors:
        name = sector.get("name", "").strip()
        if not name:
            continue
        theme_map[name] = get_theme_seed_tickers(name)

    return theme_map