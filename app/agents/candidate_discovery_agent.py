import json
from datetime import datetime
from typing import Any

from openai import AsyncOpenAI
from agents import Agent
from agents.models.openai_chatcompletions import OpenAIChatCompletionsModel

from app.config import settings
from app.prompts.candidate_discovery_prompt import CANDIDATE_DISCOVERY_PROMPT
from app.sources.universe_sources import get_theme_seed_tickers
from app.tools.company_data import get_company_profile
from app.utils.agent_runner import run_agent_with_retry
from app.utils.trader_output import extract_json_dict

_STOPWORDS = {
    "and",
    "or",
    "the",
    "to",
    "for",
    "via",
    "with",
    "into",
    "from",
    "shift",
    "timing",
    "expert",
    "analysis",
    "next",
    "months",
}

_THEME_DOMAIN_KEYWORDS: list[tuple[set[str], set[str]]] = [
    (
        {
            "semiconductor",
            "semiconductors",
            "chip",
            "chips",
            "foundry",
            "memory",
            "logic",
            "wafer",
            "fab",
            "fabrication",
            "packaging",
            "arm",
            "asic",
            "compute",
            "equipment",
            "eda",
            "networking",
            "optical",
            "photonics",
        },
        {
            "semiconductor",
            "chip",
            "chips",
            "foundry",
            "memory",
            "logic",
            "wafer",
            "fab",
            "fabrication",
            "packaging",
            "substrate",
            "equipment",
            "eda",
            "design automation",
            "processor",
            "cpu",
            "gpu",
            "asic",
            "networking",
            "optical",
            "photonics",
            "silicon",
            "electronics",
            "electronic components",
            "test equipment",
            "materials",
        },
    ),
    (
        {"power", "grid", "cooling", "electrification", "utility", "utilities", "infrastructure"},
        {
            "electrical",
            "power",
            "grid",
            "utility",
            "utilities",
            "cooling",
            "hvac",
            "infrastructure",
            "industrial",
            "capital goods",
            "electrification",
            "distribution",
            "transmission",
            "switchgear",
            "data center infrastructure",
        },
    ),
    (
        {"software", "cloud", "saas", "security"},
        {
            "software",
            "cloud",
            "saas",
            "security",
            "application software",
            "infrastructure software",
            "data analytics",
        },
    ),
    (
        {"biotech", "biotechnology", "drug", "pharma", "life", "sciences", "medtech", "healthcare"},
        {
            "biotechnology",
            "pharmaceutical",
            "drug",
            "life sciences",
            "medical",
            "healthcare",
            "therapeutic",
            "diagnostic",
        },
    ),
    (
        {"energy", "oil", "gas", "lng", "upstream", "midstream"},
        {
            "oil",
            "gas",
            "lng",
            "energy",
            "upstream",
            "midstream",
            "refining",
            "exploration",
            "production",
            "oilfield",
        },
    ),
]


def build_candidate_discovery_agent(client: AsyncOpenAI) -> Agent:
    model = OpenAIChatCompletionsModel(
        model=settings.RESEARCH_MODEL,
        openai_client=client,
    )

    return Agent(
        name="Candidate Discovery Analyst",
        model=model,
        instructions=CANDIDATE_DISCOVERY_PROMPT,
    )


def _normalize_tickers(items: list[Any]) -> list[str]:
    normalized: list[str] = []
    seen = set()
    for item in items:
        if not isinstance(item, str):
            continue
        ticker = item.upper().strip()
        if not ticker or ticker in seen:
            continue
        seen.add(ticker)
        normalized.append(ticker)
    return normalized


def _normalize_text(text: str) -> str:
    return " ".join(str(text).lower().replace("/", " ").replace("-", " ").split())


def _theme_tokens(theme: str) -> set[str]:
    return {
        token
        for token in _normalize_text(theme).split()
        if len(token) >= 4 and token not in _STOPWORDS
    }


def _theme_required_keywords(theme: str) -> set[str]:
    theme_text = _normalize_text(theme)
    theme_words = set(theme_text.split())
    required: set[str] = set()
    for triggers, keywords in _THEME_DOMAIN_KEYWORDS:
        if theme_words.intersection(triggers) or any(trigger in theme_text for trigger in triggers):
            required.update(keywords)
    return required


def _profile_relevance_score(theme: str, profile: dict[str, Any]) -> int:
    searchable_parts = [
        profile.get("company_name", ""),
        profile.get("sector", ""),
        profile.get("industry", ""),
        profile.get("business_summary", ""),
        profile.get("sec_sic_description", ""),
    ]
    profile_text = _normalize_text(" ".join(str(part) for part in searchable_parts if part))
    if not profile_text:
        return 0

    score = 0
    tokens = _theme_tokens(theme)
    required_keywords = _theme_required_keywords(theme)

    token_hits = sum(1 for token in tokens if token in profile_text)
    score += min(token_hits, 3)

    required_hits = sum(1 for keyword in required_keywords if keyword in profile_text)
    if required_hits:
        score += 3 + min(required_hits, 3)

    return score


def _validate_tickers(theme: str, tickers: list[str], seed_tickers: list[str], max_items: int = 6) -> list[str]:
    ranked: list[tuple[int, str]] = []
    seed_set = {ticker.upper().strip() for ticker in seed_tickers}

    for ticker in tickers:
        if ticker in seed_set:
            continue
        profile = get_company_profile(ticker)
        if not profile.get("enabled"):
            continue
        relevance = _profile_relevance_score(theme, profile)
        if relevance < 3:
            continue
        ranked.append((relevance, ticker))

    ranked.sort(key=lambda item: (-item[0], item[1]))
    return [ticker for _, ticker in ranked[:max_items]]


def _seed_ticker_map(research_data: dict[str, Any]) -> dict[str, list[str]]:
    theme_map: dict[str, list[str]] = {}
    sectors = research_data.get("candidate_sectors", []) + research_data.get("final_sectors", [])
    for sector in sectors:
        if not isinstance(sector, dict):
            continue
        theme_name = str(sector.get("name", "")).strip()
        if not theme_name or theme_name in theme_map:
            continue
        theme_map[theme_name] = get_theme_seed_tickers(theme_name)
    return theme_map


async def run_candidate_discovery(
    research_data: dict[str, Any],
    run_id: str,
    client: AsyncOpenAI,
) -> dict[str, Any]:
    agent = build_candidate_discovery_agent(client)
    seed_map = _seed_ticker_map(research_data)
    payload = {
        "research_summary": research_data.get("summary", ""),
        "candidate_sectors": research_data.get("candidate_sectors", []),
        "final_sectors": research_data.get("final_sectors", []),
        "seed_ticker_map": seed_map,
    }

    result = await run_agent_with_retry(agent, json.dumps(payload, ensure_ascii=False, indent=2))
    parsed = extract_json_dict(result.final_output, "Candidate Discovery")

    known_themes = set(seed_map)
    theme_candidates: list[dict[str, Any]] = []

    for item in parsed.get("theme_candidates", []):
        if not isinstance(item, dict):
            continue
        theme = str(item.get("theme", "")).strip()
        if not theme or theme not in known_themes:
            continue
        proposed = _normalize_tickers(item.get("proposed_tickers", []))
        validated = _validate_tickers(theme, proposed, seed_map.get(theme, []))
        theme_candidates.append(
            {
                "theme": theme,
                "seed_tickers": seed_map.get(theme, []),
                "validated_tickers": validated,
                "rationale": item.get("rationale", ""),
            }
        )

    return {
        "run_id": run_id,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "agent_name": "candidate_discovery",
        "model": settings.RESEARCH_MODEL,
        "raw_output": result.final_output,
        "theme_candidates": theme_candidates,
        "summary": parsed.get("summary", ""),
    }
