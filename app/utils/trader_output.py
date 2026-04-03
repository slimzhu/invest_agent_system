from __future__ import annotations

import json
import re
from typing import Any


def _strip_trailing_commas(text: str) -> str:
    return re.sub(r",(\s*[}\]])", r"\1", text)


def extract_json_dict(text: str, label: str) -> dict[str, Any]:
    raw = text.strip()

    candidates = [
        raw,
        _strip_trailing_commas(raw),
    ]

    first_brace = raw.find("{")
    last_brace = raw.rfind("}")
    if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
        chunk = raw[first_brace : last_brace + 1]
        candidates.extend([chunk, _strip_trailing_commas(chunk)])

    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            continue

    decoder = json.JSONDecoder()
    sanitized = _strip_trailing_commas(raw)
    best_obj: dict[str, Any] | None = None

    for source in (raw, sanitized):
        for i, ch in enumerate(source):
            if ch != "{":
                continue
            try:
                obj, _ = decoder.raw_decode(source[i:])
            except json.JSONDecodeError:
                continue
            if isinstance(obj, dict) and (
                best_obj is None or len(obj.keys()) > len(best_obj.keys())
            ):
                best_obj = obj

    if best_obj is not None:
        return best_obj

    raise ValueError(f"{label} 输出中未找到有效 JSON。原始输出为：\n{raw}")


def _as_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, dict):
        pieces: list[str] = []
        for key, item in value.items():
            if item in (None, "", [], {}):
                continue
            label = key.replace("_", " ").strip().title()
            pieces.append(f"{label}: {item}")
        return " ".join(pieces).strip()
    if isinstance(value, list):
        return "; ".join(str(item).strip() for item in value if str(item).strip())
    return str(value).strip()


def _as_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        text = value.strip()
        return [text] if text else []
    if value is None:
        return []
    text = str(value).strip()
    return [text] if text else []


def _coalesce(*values: Any) -> Any:
    for value in values:
        if value not in (None, "", [], {}):
            return value
    return None


def _confidence_value(*values: Any) -> float | str | None:
    value = _coalesce(*values)
    if value in (None, ""):
        return None
    try:
        numeric = float(value)
        if 1 < numeric <= 10:
            numeric = numeric / 10.0
        if numeric < 0:
            numeric = 0.0
        if numeric > 1:
            numeric = 1.0
        return round(numeric, 4)
    except (TypeError, ValueError):
        return value


def _valuation_view(value: Any) -> str:
    if isinstance(value, dict):
        parts: list[str] = []
        for key in ("pe_ttm", "pb", "ps", "relative_to_history", "intrinsic_value_comment"):
            item = value.get(key)
            if item in (None, "", [], {}):
                continue
            label = key.replace("_", " ").upper() if key in {"pb", "ps"} else key.replace("_", " ").title()
            parts.append(f"{label}: {item}")
        return " ".join(parts).strip()
    return _as_text(value)


def _split_upside_bear(value: Any) -> tuple[str, str]:
    if isinstance(value, dict):
        return _as_text(value.get("upside")), _as_text(value.get("bear"))
    text = _as_text(value)
    if "Bear:" in text and "Upside:" in text:
        upside, bear = text.split("Bear:", 1)
        return upside.replace("Upside:", "").strip(), bear.strip()
    return "", text if text and not text.lower().startswith("upside") else text


def build_company_lookup(
    compacted_evidence: dict[str, Any],
    tool_calls: list[dict[str, Any]] | None = None,
) -> dict[str, dict[str, Any]]:
    lookup: dict[str, dict[str, Any]] = {}

    for companies in compacted_evidence.get("evidence_by_theme", {}).values():
        if not isinstance(companies, list):
            continue
        for company in companies:
            if not isinstance(company, dict):
                continue
            ticker = str(company.get("ticker", "")).upper().strip()
            if not ticker:
                continue
            profile = company.get("company_profile", {})
            lookup[ticker] = {
                "company_name": profile.get("company_name", ""),
                "sector_theme": "",
            }

    for theme_name, companies in compacted_evidence.get("evidence_by_theme", {}).items():
        if not isinstance(companies, list):
            continue
        for company in companies:
            if not isinstance(company, dict):
                continue
            ticker = str(company.get("ticker", "")).upper().strip()
            if ticker and ticker in lookup and not lookup[ticker].get("sector_theme"):
                lookup[ticker]["sector_theme"] = theme_name

    for call in tool_calls or []:
        ticker = str(call.get("ticker", "")).upper().strip()
        output = call.get("output", {})
        if not ticker:
            continue
        if ticker not in lookup:
            lookup[ticker] = {"company_name": "", "sector_theme": ""}
        if isinstance(output, dict) and output.get("company_name"):
            lookup[ticker]["company_name"] = output.get("company_name", "")

    return lookup


def normalize_selected_stock(
    stock: dict[str, Any],
    *,
    company_lookup: dict[str, dict[str, Any]] | None = None,
    default_rating: str = "",
) -> dict[str, Any]:
    lookup = company_lookup or {}
    ticker = str(stock.get("ticker", "")).upper().strip()
    meta = lookup.get(ticker, {})

    upside_case = _as_text(stock.get("upside_case"))
    bear_case = _as_text(stock.get("bear_case"))
    if not upside_case and not bear_case:
        upside_case, bear_case = _split_upside_bear(stock.get("upside_bear_case"))

    normalized = {
        "ticker": ticker,
        "company_name": _coalesce(stock.get("company_name"), meta.get("company_name"), ""),
        "sector_theme": _coalesce(stock.get("sector_theme"), meta.get("sector_theme"), ""),
        "rating": _coalesce(stock.get("rating"), stock.get("final_rating"), default_rating),
        "confidence": _confidence_value(stock.get("confidence"), stock.get("final_rating_confidence")),
        "style_fit": _coalesce(
            _as_text(stock.get("business_quality")),
            _as_text(stock.get("business_quality_growth_exposure")),
            _as_text(stock.get("business_quality_macro_exposure")),
            _as_text(stock.get("business_quality_event_exposure")),
            "",
        ),
        "business_quality": _coalesce(
            _as_text(stock.get("business_quality")),
            _as_text(stock.get("business_quality_growth_exposure")),
            _as_text(stock.get("business_quality_macro_exposure")),
            _as_text(stock.get("business_quality_event_exposure")),
            "",
        ),
        "financial_strength": _as_text(stock.get("financial_strength")),
        "valuation_view": _valuation_view(stock.get("valuation")),
        "valuation": stock.get("valuation", {}),
        "why_this_stock": _coalesce(
            _as_text(stock.get("why_this_stock")),
            _as_text(stock.get("differentiation")),
            _as_text(stock.get("regime_linkage")),
            _as_text(stock.get("market_cap_tier_maturity")),
            _as_text(stock.get("next_catalyst")),
            "",
        ),
        "why_now": _as_text(stock.get("why_now")),
        "risks": _coalesce(_as_text(stock.get("risks")), ""),
        "catalysts": stock.get("catalysts", {}),
        "upside_case": upside_case,
        "bear_case": bear_case,
        "key_risks": _as_list(stock.get("key_risks")),
        "invalidation_conditions": _as_list(stock.get("invalidation_conditions")),
        "scenario_analysis": _coalesce(
            _as_text(stock.get("scenario_analysis")),
            _as_text(stock.get("scenario_sensitivity")),
            _as_text(stock.get("sensitivity_analysis")),
            "",
        ),
        "evidence_used": _as_list(stock.get("evidence_used")) or [
            "recent_filings",
            "filing_analysis",
            "fundamentals_summary",
            "recent_news",
            "market_snapshot",
            "ir_materials",
        ],
        "differentiation": _coalesce(
            _as_text(stock.get("differentiation")),
            _as_text(stock.get("regime_linkage")),
            _as_text(stock.get("market_cap_tier_maturity")),
            _as_text(stock.get("next_catalyst")),
            "",
        ),
        "raw_model_fields": stock,
    }

    return normalized


def normalize_watch_stock(
    stock: dict[str, Any],
    *,
    company_lookup: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    lookup = company_lookup or {}
    ticker = str(stock.get("ticker", "")).upper().strip()
    meta = lookup.get(ticker, {})

    return {
        "ticker": ticker,
        "company_name": _coalesce(stock.get("company_name"), meta.get("company_name"), ""),
        "sector_theme": _coalesce(stock.get("sector_theme"), meta.get("sector_theme"), ""),
        "reason_for_monitoring": _coalesce(
            _as_text(stock.get("reason_for_monitoring")),
            _as_text(stock.get("reason")),
            "",
        ),
        "evidence_used": _as_list(stock.get("evidence_used")) or [
            "recent_filings",
            "filing_analysis",
            "fundamentals_summary",
            "recent_news",
            "market_snapshot",
            "ir_materials",
        ],
        "raw_model_fields": stock,
    }
