import json
from datetime import datetime
from typing import Any

from agents import Agent, RunContextWrapper, function_tool

from app.config import settings
from app.prompts.trader_event_prompt import (
    EVENT_TRADER_PROMPT,
    EVENT_TRADER_SECTOR_REVIEW_PROMPT,
)
from app.tools.company_data import get_company_profile
from app.utils.agent_runner import run_agent_with_retry
from app.utils.trader_output import (
    build_company_lookup,
    extract_json_dict,
    normalize_selected_stock,
    normalize_watch_stock,
)

from app.tools.universe_builder import build_stock_universe_from_sectors
from app.tools.evidence_pack_builder import build_evidence_pack, filter_evidence_pack_by_sectors
from app.tools.evidence_compactor import compact_evidence_pack

class EventTraderContext:
    def __init__(self) -> None:
        self.tool_calls: list[dict[str, Any]] = []


@function_tool
def company_profile_tool(
    wrapper: RunContextWrapper[EventTraderContext],
    ticker: str,
) -> str:
    """
    Get a live company snapshot for a U.S. stock ticker using configured data sources.
    """
    profile = get_company_profile(ticker)

    wrapper.context.tool_calls.append(
        {
            "tool_name": "company_profile_tool",
            "ticker": ticker.upper().strip(),
            "output": profile,
        }
    )

    return json.dumps(profile, ensure_ascii=False, indent=2)


def build_event_trader_agent() -> Agent:
    return Agent(
        name="Event Trader",
        model=settings.EVENT_TRADER_MODEL,
        instructions=EVENT_TRADER_PROMPT,
        tools=[company_profile_tool],
    )


def build_event_sector_review_agent() -> Agent:
    return Agent(
        name="Event Trader Sector Reviewer",
        model=settings.EVENT_TRADER_MODEL,
        instructions=EVENT_TRADER_SECTOR_REVIEW_PROMPT,
    )


def extract_json_from_text(text: str) -> dict[str, Any]:
    return extract_json_dict(text, "Event Trader")


def _normalize_sector_names(names: list[Any]) -> list[str]:
    normalized: list[str] = []
    seen = set()
    for item in names:
        if not isinstance(item, str):
            continue
        name = item.strip()
        if not name or name in seen:
            continue
        seen.add(name)
        normalized.append(name)
    return normalized


async def review_event_sectors(research_data: dict[str, Any]) -> dict[str, Any]:
    agent = build_event_sector_review_agent()
    payload = {
        "research_summary": research_data.get("summary", ""),
        "candidate_sectors": research_data.get("candidate_sectors", []),
        "final_sectors": research_data.get("final_sectors", []),
    }
    result = await run_agent_with_retry(agent, json.dumps(payload, ensure_ascii=False, indent=2))
    parsed = extract_json_from_text(result.final_output)

    final_names = _normalize_sector_names([sector.get("name", "") for sector in research_data.get("final_sectors", [])])
    candidate_names = _normalize_sector_names([sector.get("name", "") for sector in research_data.get("candidate_sectors", [])])
    sector_lookup = {
        sector.get("name", "").strip(): sector
        for sector in research_data.get("candidate_sectors", []) + research_data.get("final_sectors", [])
        if isinstance(sector, dict) and sector.get("name", "").strip()
    }

    chosen_names = _normalize_sector_names(parsed.get("chosen_sectors", []))
    valid_names = [name for name in chosen_names if name in sector_lookup]
    if not valid_names:
        valid_names = final_names[:3] if final_names else candidate_names[:3]

    accepted = [name for name in _normalize_sector_names(parsed.get("accepted_sectors", [])) if name in final_names]
    rejected = [name for name in _normalize_sector_names(parsed.get("rejected_sectors", [])) if name in final_names]
    replacements = [name for name in _normalize_sector_names(parsed.get("replacement_sectors", [])) if name in candidate_names]

    return {
        "sector_review_decision": parsed.get("sector_review_decision", "accept"),
        "accepted_sectors": accepted or [name for name in valid_names if name in final_names],
        "rejected_sectors": rejected,
        "replacement_sectors": replacements,
        "chosen_sectors": [sector_lookup[name] for name in valid_names],
        "sector_review_reason": parsed.get("sector_review_reason", ""),
    }


def build_event_trader_input(
    research_data: dict[str, Any],
    chosen_sectors: list[dict[str, Any]],
    shared_evidence_pack: dict[str, Any] | None = None,
    analysis_mode: str = "sector",
    target_ticker: str | None = None,
) -> tuple[str, dict[str, Any], dict[str, dict[str, Any]]]:
    if shared_evidence_pack is None:
        universe_data = build_stock_universe_from_sectors(chosen_sectors)
        evidence_pack = build_evidence_pack(universe_data)
    else:
        evidence_pack = filter_evidence_pack_by_sectors(shared_evidence_pack, chosen_sectors)
    compacted_evidence = compact_evidence_pack(
        evidence_pack,
        max_companies_per_theme=4,
    )

    payload = {
        "research_summary": research_data.get("summary", ""),
        "candidate_sectors": research_data.get("candidate_sectors", []),
        "final_sectors": research_data.get("final_sectors", []),
        "chosen_sectors": chosen_sectors,
        "evidence_pack": compacted_evidence,
        "analysis_mode": analysis_mode,
        "task": "",
    }

    if analysis_mode == "single_stock":
        payload["target_ticker"] = (target_ticker or "").upper().strip()
        payload["task"] = (
            f"Analyze exactly one user-selected stock: {(target_ticker or '').upper().strip()}. "
            "Return exactly one selected stock entry for that ticker only, and rate it BUY, WATCH, or SELL from an event / catalyst perspective. "
            "Do not substitute another ticker. "
            "Treat this as an investment underwriting task, not an information gathering task. "
            "Use the latest filings, filing analysis, IR/transcript links, structured fundamentals, market snapshot, and recent catalysts from the evidence pack as your primary basis."
        )
    else:
        payload["task"] = (
            "Based on the approved sectors/themes and the provided compact evidence pack, "
            "identify 2 to 6 potentially investable U.S. stocks from an event / catalyst perspective, with fewer only if evidence is weak and never more than 9 total. "
            "You must stay within the approved sectors only. "
            "Treat this as an investment underwriting task, not an information gathering task. "
            "Use the latest filings, filing analysis, IR/transcript links, structured fundamentals, market snapshot, and recent catalysts from the evidence pack as your primary basis. "
            "Actively consider smaller or less-covered names if the next catalyst can move the stock more than it would move an already recognized mega-cap leader."
        )

    payload_str = json.dumps(payload, ensure_ascii=False, indent=2)
    company_lookup = build_company_lookup(compacted_evidence)
    return payload_str[:120000], compacted_evidence.get("data_availability", {}), company_lookup

async def run_event_trader(
    research_data: dict[str, Any],
    run_id: str,
    shared_evidence_pack: dict[str, Any] | None = None,
    analysis_mode: str = "sector",
    target_ticker: str | None = None,
) -> dict[str, Any]:
    agent = build_event_trader_agent()
    sector_review = await review_event_sectors(research_data)
    user_input, data_availability, company_lookup = build_event_trader_input(
        research_data,
        sector_review["chosen_sectors"],
        shared_evidence_pack=shared_evidence_pack,
        analysis_mode=analysis_mode,
        target_ticker=target_ticker,
    )
    context = EventTraderContext()

    result = await run_agent_with_retry(agent, user_input, context=context)
    raw_output = result.final_output
    parsed = extract_json_from_text(raw_output)

    data = {
        "run_id": run_id,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "agent_name": "trader_event",
        "model": settings.EVENT_TRADER_MODEL,
        "user_input": user_input,
        "raw_output": raw_output,
        "decision": parsed.get("decision", ""),
        "style": parsed.get("style", "event_catalyst"),
        "sector_review_decision": sector_review.get("sector_review_decision", "accept"),
        "accepted_sectors": sector_review.get("accepted_sectors", []),
        "rejected_sectors": sector_review.get("rejected_sectors", []),
        "replacement_sectors": sector_review.get("replacement_sectors", []),
        "chosen_sectors": parsed.get("selected_sectors", []) or [
            sector.get("name", "") for sector in sector_review.get("chosen_sectors", [])
        ],
        "sector_review_reason": sector_review.get("sector_review_reason", ""),
        "selected_stocks": [
            normalize_selected_stock(
                stock,
                company_lookup=company_lookup,
                default_rating=parsed.get("decision", ""),
            )
            for stock in parsed.get("selected_stocks", [])
            if isinstance(stock, dict)
        ],
        "watch_stocks": [
            normalize_watch_stock(stock, company_lookup=company_lookup)
            for stock in parsed.get("watch_stocks", [])
            if isinstance(stock, dict)
        ],
        "summary": parsed.get("summary", ""),
        "tool_calls": context.tool_calls,
        "data_availability": data_availability,
        "analysis_mode": analysis_mode,
        "target_ticker": (target_ticker or "").upper().strip(),
    }

    return data
