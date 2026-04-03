import json
from collections import Counter
from datetime import datetime
from typing import Any

from agents import Agent

from app.config import settings
from app.prompts.validator_prompt import VALIDATOR_PROMPT
from app.utils.agent_runner import run_agent_with_retry
from app.utils.trader_output import extract_json_dict


def build_validator_agent() -> Agent:
    return Agent(
        name="Validator",
        model=settings.VALIDATOR_MODEL,
        instructions=VALIDATOR_PROMPT,
    )


def extract_json_from_text(text: str) -> dict[str, Any]:
    return extract_json_dict(text, "Validator")


def build_validator_input(
    research_data: dict[str, Any],
    value_data: dict[str, Any],
    growth_data: dict[str, Any],
    macro_data: dict[str, Any],
    event_data: dict[str, Any],
) -> str:
    trader_map = {
        "value": value_data,
        "growth": growth_data,
        "macro": macro_data,
        "event": event_data,
    }

    def _trader_payload(trader_data: dict[str, Any]) -> dict[str, Any]:
        return {
            "decision": trader_data.get("decision", ""),
            "style": trader_data.get("style", ""),
            "sector_review_decision": trader_data.get("sector_review_decision", ""),
            "accepted_sectors": trader_data.get("accepted_sectors", []),
            "rejected_sectors": trader_data.get("rejected_sectors", []),
            "replacement_sectors": trader_data.get("replacement_sectors", []),
            "chosen_sectors": trader_data.get("chosen_sectors", []),
            "sector_review_reason": trader_data.get("sector_review_reason", ""),
            "selected_stocks": trader_data.get("selected_stocks", []),
            "watch_stocks": trader_data.get("watch_stocks", []),
            "summary": trader_data.get("summary", ""),
            "tool_calls": trader_data.get("tool_calls", []),
            "data_availability": trader_data.get("data_availability", {}),
        }

    expected_positions: list[dict[str, Any]] = []
    for trader_name, trader_data in trader_map.items():
        for stock in trader_data.get("selected_stocks", []):
            if not isinstance(stock, dict):
                continue
            expected_positions.append(
                {
                    "trader": trader_name,
                    "style": trader_data.get("style", ""),
                    "ticker": stock.get("ticker", ""),
                    "company_name": stock.get("company_name", ""),
                    "sector_theme": stock.get("sector_theme", ""),
                    "rating": stock.get("rating", ""),
                    "confidence": stock.get("confidence", ""),
                    "why_this_stock": stock.get("why_this_stock", ""),
                    "differentiation": stock.get("differentiation", ""),
                }
            )

    overlap_counter = Counter(
        position.get("ticker", "") for position in expected_positions if position.get("ticker")
    )
    overlap_summary = [
        {
            "ticker": ticker,
            "count": count,
            "traders": [
                position.get("trader")
                for position in expected_positions
                if position.get("ticker") == ticker
            ],
        }
        for ticker, count in overlap_counter.items()
        if count > 1
    ]

    payload = {
        "research_output": {
            "summary": research_data.get("summary", ""),
            "candidate_sectors": research_data.get("candidate_sectors", []),
            "final_sectors": research_data.get("final_sectors", []),
        },
        "expected_validated_stock_count": len(expected_positions),
        "expected_positions": expected_positions,
        "overlap_summary": overlap_summary,
        "trader_outputs": {
            trader_name: _trader_payload(trader_data)
            for trader_name, trader_data in trader_map.items()
        },
        "task": (
            "Review the researcher output and all four trader portfolios critically. "
            "Determine whether each stock should be approved, watchlisted, or rejected, "
            "and also evaluate each trader's style discipline, sector review quality, "
            "whether cross-trader overlap is justified, and whether homogeneity or style drift should be penalized. "
            "You must review every selected stock position listed in expected_positions."
        ),
    }

    return json.dumps(payload, ensure_ascii=False, indent=2)


def _normalize_validated_stocks(
    parsed: dict[str, Any],
    trader_map: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    expected: dict[tuple[str, str], dict[str, Any]] = {}
    for trader_name, trader_data in trader_map.items():
        for stock in trader_data.get("selected_stocks", []):
            if not isinstance(stock, dict):
                continue
            ticker = str(stock.get("ticker", "")).upper().strip()
            if not ticker:
                continue
            expected[(trader_name, ticker)] = {
                "ticker": ticker,
                "trader": trader_name,
                "style": trader_data.get("style", ""),
                "sector_theme": stock.get("sector_theme", ""),
            }

    normalized: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()

    for item in parsed.get("validated_stocks", []):
        if not isinstance(item, dict):
            continue
        trader = str(item.get("trader", "")).strip().lower()
        ticker = str(item.get("ticker", "")).upper().strip()
        key = (trader, ticker)
        if key not in expected or key in seen:
            continue
        seen.add(key)
        normalized.append(
            {
                "ticker": ticker,
                "trader": trader,
                "style": item.get("style") or expected[key].get("style", ""),
                "decision": item.get("decision", "watchlist"),
                "verdict": item.get("verdict", ""),
                "strengths": item.get("strengths", []),
                "concerns": item.get("concerns", []),
                "confidence_adjustment": item.get("confidence_adjustment", "lower"),
                "sector_alignment": item.get("sector_alignment", expected[key].get("sector_theme", "")),
                "evidence_quality": item.get("evidence_quality", "medium"),
            }
        )

    for key, meta in expected.items():
        if key in seen:
            continue
        normalized.append(
            {
                "ticker": meta["ticker"],
                "trader": meta["trader"],
                "style": meta["style"],
                "decision": "watchlist",
                "verdict": "Validator did not explicitly review this selected stock, so it is downgraded pending manual review.",
                "strengths": [],
                "concerns": [
                    "Validator coverage was incomplete for this selected stock.",
                    "Automatic downgrade applied until a full review is produced.",
                ],
                "confidence_adjustment": "lower",
                "sector_alignment": meta.get("sector_theme", ""),
                "evidence_quality": "medium",
            }
        )

    return normalized


def _normalize_trader_scorecards(
    parsed: dict[str, Any],
    trader_map: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    expected = {
        trader_name: {
            "trader": trader_name,
            "style": trader_data.get("style", ""),
        }
        for trader_name, trader_data in trader_map.items()
    }

    normalized: list[dict[str, Any]] = []
    seen: set[str] = set()

    for item in parsed.get("trader_scorecards", []):
        if not isinstance(item, dict):
            continue
        trader = str(item.get("trader", "")).strip().lower()
        if trader not in expected or trader in seen:
            continue
        seen.add(trader)
        normalized.append(
            {
                "trader": trader,
                "style": item.get("style") or expected[trader].get("style", ""),
                "decision_review": item.get("decision_review", "watchlist"),
                "style_discipline": item.get("style_discipline", "medium"),
                "sector_review_verdict": item.get("sector_review_verdict", ""),
                "portfolio_concerns": item.get("portfolio_concerns", []),
                "portfolio_strengths": item.get("portfolio_strengths", []),
            }
        )

    for trader, meta in expected.items():
        if trader in seen:
            continue
        normalized.append(
            {
                "trader": trader,
                "style": meta.get("style", ""),
                "decision_review": "watchlist",
                "style_discipline": "weak",
                "sector_review_verdict": "Validator did not produce a scorecard for this trader.",
                "portfolio_concerns": [
                    "Missing validator scorecard.",
                ],
                "portfolio_strengths": [],
            }
        )

    return normalized


def _normalize_overall_decision(parsed: dict[str, Any], validated_stocks: list[dict[str, Any]]) -> str:
    decisions = [item.get("decision", "") for item in validated_stocks]
    if "reject" in decisions:
        return "reject"
    if "watchlist" in decisions:
        return "watchlist"
    overall = parsed.get("overall_decision", "")
    return overall or "approve"


async def run_validator(
    research_data: dict[str, Any],
    value_data: dict[str, Any],
    growth_data: dict[str, Any],
    macro_data: dict[str, Any],
    event_data: dict[str, Any],
    run_id: str,
) -> dict[str, Any]:
    agent = build_validator_agent()
    trader_map = {
        "value": value_data,
        "growth": growth_data,
        "macro": macro_data,
        "event": event_data,
    }
    user_input = build_validator_input(
        research_data,
        value_data,
        growth_data,
        macro_data,
        event_data,
    )

    result = await run_agent_with_retry(agent, user_input)
    raw_output = result.final_output
    parsed = extract_json_from_text(raw_output)
    validated_stocks = _normalize_validated_stocks(parsed, trader_map)
    trader_scorecards = _normalize_trader_scorecards(parsed, trader_map)
    overall_decision = _normalize_overall_decision(parsed, validated_stocks)
    cross_trader_observations = parsed.get("cross_trader_observations", [])
    if not cross_trader_observations:
        cross_trader_observations = [
            "Validator did not return cross-trader observations explicitly.",
        ]

    data = {
        "run_id": run_id,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "agent_name": "validator",
        "model": settings.VALIDATOR_MODEL,
        "user_input": user_input,
        "raw_output": raw_output,
        "overall_decision": overall_decision,
        "portfolio_verdict": parsed.get("portfolio_verdict", ""),
        "validated_stocks": validated_stocks,
        "trader_scorecards": trader_scorecards,
        "cross_trader_observations": cross_trader_observations,
        "summary": parsed.get("summary", ""),
    }

    return data
