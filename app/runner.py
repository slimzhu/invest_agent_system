from pathlib import Path
import json
from datetime import datetime
from typing import Any, Callable

from app.agents.research_agent import run_research_from_signals
from app.agents.research_signal_agent import run_signal_extractor
from app.agents.candidate_discovery_agent import run_candidate_discovery
from app.agents.trader_value_agent import run_value_trader
from app.agents.trader_growth_agent import run_growth_trader
from app.agents.trader_macro_agent import run_macro_trader
from app.agents.trader_event_agent import run_event_trader
from app.agents.validator_agent import run_validator
from app.tools.company_data import get_company_profile
from app.tools.evidence_pack_builder import build_evidence_pack
from app.tools.universe_builder import build_stock_universe_for_trader_pool
from app.sources.research_sources import (
    get_brave_search_results,
    get_finnhub_company_news,
    get_finnhub_market_news,
    get_sec_company_facts,
    get_sec_company_submissions,
)
from app.sources.universe_sources import get_theme_seed_tickers
from app.tools.filings_collector import get_cik_for_ticker
from app.storage import (
    save_research_step,
    save_value_trader_step,
    save_growth_trader_step,
    save_macro_trader_step,
    save_event_trader_step,
    save_validator_step,
)


StepCallback = Callable[[str, dict[str, Any]], None]


def _notify_step(
    step_callback: StepCallback | None,
    step_key: str,
    data: dict[str, Any] | None = None,
    dir_path: Path | str | None = None,
    status: str = "completed",
    error: str | None = None,
) -> None:
    if step_callback is None:
        return
    payload: dict[str, Any] = {
        "status": status,
        "data": data or {},
    }
    if dir_path is not None:
        payload["dir"] = str(dir_path)
    if error:
        payload["error"] = error
    step_callback(step_key, payload)


def _error_payload(step: str, exc: Exception) -> dict[str, str]:
    return {
        "step": step,
        "message": f"{type(exc).__name__}: {exc}",
    }


def parse_ticker_list(raw_value: str) -> list[str]:
    tickers: list[str] = []
    seen = set()
    normalized = raw_value.replace("\n", ",").replace(" ", ",")
    for item in normalized.split(","):
        ticker = item.upper().strip()
        if not ticker or ticker in seen:
            continue
        seen.add(ticker)
        tickers.append(ticker)
    return tickers


def summarize_research_source_bundle(source_bundle: dict[str, object]) -> dict[str, object]:
    def summarize_single_source(item: object, item_key: str) -> dict[str, object]:
        if not isinstance(item, dict):
            return {"enabled": False, "item_count": 0, "error": "Invalid source payload"}
        value = item.get(item_key, [])
        item_count = len(value) if isinstance(value, list) else 0
        return {
            "enabled": bool(item.get("enabled", True)),
            "item_count": item_count,
            "error": item.get("error") or item.get("reason"),
        }

    def summarize_group(items: object, item_key: str) -> dict[str, object]:
        if not isinstance(items, list):
            return {"total": 0, "available": 0, "missing": 0}
        total = len(items)
        available = 0
        total_items = 0
        errors: list[str] = []
        for item in items:
            summary = summarize_single_source(item, item_key)
            if summary["enabled"]:
                available += 1
            else:
                error = summary.get("error")
                if isinstance(error, str) and error:
                    errors.append(error)
            total_items += int(summary["item_count"])
        return {
            "total": total,
            "available": available,
            "missing": total - available,
            "item_count": total_items,
            "sample_errors": errors[:3],
        }

    return {
        "macro_news": summarize_single_source(source_bundle.get("macro_news"), "articles"),
        "company_news_signals": summarize_group(source_bundle.get("company_news_signals"), "articles"),
        "thematic_search_results": summarize_group(source_bundle.get("thematic_search_results"), "results"),
        "social_signal_results": summarize_group(source_bundle.get("social_signal_results"), "results"),
        "sec_validation_samples": summarize_group(source_bundle.get("sec_validation_samples"), "recent_forms"),
    }


def build_research_input() -> tuple[str, dict[str, object]]:
    source_bundle = {
        "macro_news": get_finnhub_market_news(category="general", limit=6),
        "company_news_signals": [
            get_finnhub_company_news("NVDA", days_back=21, limit=5),
            get_finnhub_company_news("AVGO", days_back=21, limit=5),
            get_finnhub_company_news("ANET", days_back=21, limit=5),
            get_finnhub_company_news("MU", days_back=21, limit=5),
            get_finnhub_company_news("LLY", days_back=21, limit=5),
            get_finnhub_company_news("XOM", days_back=21, limit=5),
            get_finnhub_company_news("CAT", days_back=21, limit=5),
            get_finnhub_company_news("ETN", days_back=21, limit=5),
        ],
        "thematic_search_results": [
            get_brave_search_results("AI infrastructure outlook next 12 months", count=4),
            get_brave_search_results("optical networking demand outlook next 12 months", count=4),
            get_brave_search_results("memory cycle DRAM NAND outlook next 12 months", count=4),
            get_brave_search_results("power grid investment outlook U.S. next 12 months", count=4),
            get_brave_search_results("data center cooling and power equipment outlook", count=4),
            get_brave_search_results("GLP-1 demand outlook next 12 months", count=4),
            get_brave_search_results("industrial automation outlook U.S. next 12 months", count=4),
            get_brave_search_results("defense spending outlook U.S. and Europe next 12 months", count=4),
            get_brave_search_results("LNG and upstream energy capex outlook next 12 months", count=4),
            get_brave_search_results("semiconductor equipment outlook next 12 months", count=4),
        ],
        "social_signal_results": [
            get_brave_search_results("AI infrastructure investing thesis x.com OR twitter", count=4),
            get_brave_search_results("memory cycle investing thesis substack", count=4),
            get_brave_search_results("optical networking outlook substack OR x.com", count=4),
            get_brave_search_results("power equipment data center demand blog analysis", count=4),
        ],
        "sec_validation_samples": [
            get_sec_company_submissions("1045810"),
            get_sec_company_submissions("1730168"),
            get_sec_company_facts("723125"),
            get_sec_company_facts("59478"),
            get_sec_company_submissions("34088"),
            get_sec_company_submissions("1551182"),
        ],
        "task": (
            "Broadly scan global listed sector/theme opportunities, including global leaders and U.S.-listed ADRs, and identify 8 to 12 candidates first, "
            "then narrow them to the best 3 non-consensus, alpha-oriented opportunities over the next 3 to 12 months."
        ),
    }

    return (
        json.dumps(source_bundle, ensure_ascii=False, indent=2),
        summarize_research_source_bundle(source_bundle),
    )


def _build_sec_validation_samples(tickers: list[str], max_pairs: int = 3) -> list[dict[str, object]]:
    samples: list[dict[str, object]] = []
    count = 0
    for ticker in tickers:
        cik = get_cik_for_ticker(ticker)
        if not cik:
            continue
        samples.append(get_sec_company_submissions(cik))
        samples.append(get_sec_company_facts(cik))
        count += 1
        if count >= max_pairs:
            break
    return samples


def build_industry_research_input(industry: str) -> tuple[str, dict[str, object]]:
    industry_name = industry.strip()
    seed_tickers = get_theme_seed_tickers(industry_name)[:6]

    source_bundle = {
        "macro_news": get_finnhub_market_news(category="general", limit=6),
        "company_news_signals": [
            get_finnhub_company_news(ticker, days_back=21, limit=5)
            for ticker in seed_tickers
        ],
        "thematic_search_results": [
            get_brave_search_results(f"{industry_name} outlook next 12 months", count=4),
            get_brave_search_results(f"{industry_name} demand outlook next 12 months", count=4),
            get_brave_search_results(f"{industry_name} earnings outlook next 12 months", count=4),
            get_brave_search_results(f"{industry_name} capex outlook next 12 months", count=4),
            get_brave_search_results(f"{industry_name} valuation outlook next 12 months", count=4),
        ],
        "social_signal_results": [
            get_brave_search_results(f"{industry_name} investing thesis x.com OR twitter", count=4),
            get_brave_search_results(f"{industry_name} outlook substack OR blog analysis", count=4),
        ],
        "sec_validation_samples": _build_sec_validation_samples(seed_tickers),
        "task": (
            f"Analyze the user-selected industry '{industry_name}'. "
            "Identify the most investable subsectors, bottlenecks, beneficiaries, and asymmetric opportunities within this industry over the next 3 to 12 months. "
            "You are allowed to surface global industry leaders and U.S.-listed ADRs, not only U.S. domestic issuers."
        ),
        "user_selected_industry": industry_name,
        "seed_tickers": seed_tickers,
    }

    return (
        json.dumps(source_bundle, ensure_ascii=False, indent=2),
        summarize_research_source_bundle(source_bundle),
    )


def _merge_tickers(base: list[str], extra: list[str], max_items: int = 14) -> list[str]:
    merged: list[str] = []
    seen = set()
    for ticker in base + extra:
        if not isinstance(ticker, str):
            continue
        value = ticker.upper().strip()
        if not value or value in seen:
            continue
        seen.add(value)
        merged.append(value)
        if len(merged) >= max_items:
            break
    return merged


def enrich_research_data_with_discovery(
    research_data: dict[str, object],
    discovery_data: dict[str, object],
) -> dict[str, object]:
    discovered_map = {
        item.get("theme", ""): item.get("validated_tickers", [])
        for item in discovery_data.get("theme_candidates", [])
        if isinstance(item, dict) and item.get("theme")
    }

    enriched = dict(research_data)
    for key in ("candidate_sectors", "final_sectors"):
        updated_sectors: list[dict[str, object]] = []
        for sector in enriched.get(key, []):
            if not isinstance(sector, dict):
                continue
            theme_name = str(sector.get("name", "")).strip()
            seed_tickers = get_theme_seed_tickers(theme_name)
            discovered_tickers = discovered_map.get(theme_name, [])
            updated_sector = dict(sector)
            updated_sector["tickers"] = _merge_tickers(seed_tickers, discovered_tickers)
            updated_sectors.append(updated_sector)
        enriched[key] = updated_sectors

    enriched["candidate_discovery"] = discovery_data
    return enriched


def build_single_stock_context(ticker: str, run_id: str) -> tuple[dict[str, object], dict[str, object]]:
    normalized_ticker = ticker.upper().strip()
    profile = get_company_profile(normalized_ticker)
    company_name = profile.get("company_name") or normalized_ticker
    sector_name = f"Direct Analysis: {company_name} ({normalized_ticker})"
    summary = (
        f"User requested direct single-stock analysis for {company_name} ({normalized_ticker}). "
        f"Industry context: {profile.get('industry') or profile.get('sector') or 'N/A'}. "
        "All trader agents should evaluate this exact stock only, using the live evidence pack as the basis."
    )
    research_data = {
        "run_id": run_id,
        "created_at": datetime.now().isoformat(timespec='seconds'),
        "agent_name": "manual_stock_input",
        "model": "manual_input",
        "signal_input": {
            "user_selected_stock": normalized_ticker,
            "company_profile": profile,
        },
        "candidate_sectors": [
            {
                "name": sector_name,
                "decision": "accept",
                "reason": "User requested direct stock analysis.",
            }
        ],
        "final_sectors": [
            {
                "name": sector_name,
                "thesis": profile.get("business_summary", ""),
                "why_now": profile.get("market_position", ""),
                "drivers": {
                    "short_term": [profile.get("valuation_notes", "")] if profile.get("valuation_notes") else [],
                    "medium_term": [profile.get("revenue_characteristics", "")] if profile.get("revenue_characteristics") else [],
                    "long_term": [profile.get("profitability_notes", "")] if profile.get("profitability_notes") else [],
                },
                "risks": {
                    "short_term": profile.get("key_risks", []),
                    "medium_term": [],
                    "long_term": [],
                },
                "alpha_potential": "medium",
                "positioning": profile.get("market_position", ""),
                "catalyst": profile.get("valuation_notes", ""),
                "conviction": 8,
            }
        ],
        "summary": summary,
    }
    universe_data = {
        "themes": [{"name": sector_name}],
        "theme_ticker_map": {sector_name: [normalized_ticker]},
        "all_candidate_tickers": [normalized_ticker],
    }
    shared_evidence_pack = build_evidence_pack(universe_data, ticker_cache={})
    if not shared_evidence_pack.get("evidence_by_theme", {}).get(sector_name):
        shared_evidence_pack = build_evidence_pack(
            universe_data,
            ticker_cache={},
            strict_readiness=False,
        )
    return research_data, shared_evidence_pack


async def _run_trader_and_validator_steps(
    run_id: str,
    research_data: dict[str, object],
    shared_evidence_pack: dict[str, object],
    analysis_mode: str = "sector",
    target_ticker: str | None = None,
    step_callback: StepCallback | None = None,
) -> dict[str, object]:
    outputs: dict[str, object] = {
        "research": research_data,
    }
    dirs: dict[str, object] = {}

    if not shared_evidence_pack:
        trader_universe = build_stock_universe_for_trader_pool(research_data)
        shared_ticker_cache: dict[str, dict[str, object]] = {}
        shared_evidence_pack = build_evidence_pack(
            trader_universe,
            ticker_cache=shared_ticker_cache,
        )

    try:
        print("STEP 4: Value trader...")
        value_data = await run_value_trader(
            research_data,
            run_id,
            shared_evidence_pack=shared_evidence_pack,
            analysis_mode=analysis_mode,
            target_ticker=target_ticker,
        )
        value_dir = save_value_trader_step(run_id, value_data)
        outputs["value"] = value_data
        dirs["value_dir"] = value_dir
        _notify_step(step_callback, "value", value_data, value_dir)
    except Exception as exc:
        error = _error_payload("value", exc)
        _notify_step(step_callback, "value", status="failed", error=error["message"])
        return {"outputs": outputs, "dirs": dirs, "status": "failed", "error": error}

    try:
        print("STEP 5: Growth trader...")
        growth_data = await run_growth_trader(
            research_data,
            run_id,
            shared_evidence_pack=shared_evidence_pack,
            analysis_mode=analysis_mode,
            target_ticker=target_ticker,
        )
        growth_dir = save_growth_trader_step(run_id, growth_data)
        outputs["growth"] = growth_data
        dirs["growth_dir"] = growth_dir
        _notify_step(step_callback, "growth", growth_data, growth_dir)
    except Exception as exc:
        error = _error_payload("growth", exc)
        _notify_step(step_callback, "growth", status="failed", error=error["message"])
        return {"outputs": outputs, "dirs": dirs, "status": "failed", "error": error}

    try:
        print("STEP 6: Macro trader...")
        macro_data = await run_macro_trader(
            research_data,
            run_id,
            shared_evidence_pack=shared_evidence_pack,
            analysis_mode=analysis_mode,
            target_ticker=target_ticker,
        )
        macro_dir = save_macro_trader_step(run_id, macro_data)
        outputs["macro"] = macro_data
        dirs["macro_dir"] = macro_dir
        _notify_step(step_callback, "macro", macro_data, macro_dir)
    except Exception as exc:
        error = _error_payload("macro", exc)
        _notify_step(step_callback, "macro", status="failed", error=error["message"])
        return {"outputs": outputs, "dirs": dirs, "status": "failed", "error": error}

    try:
        print("STEP 7: Event trader...")
        event_data = await run_event_trader(
            research_data,
            run_id,
            shared_evidence_pack=shared_evidence_pack,
            analysis_mode=analysis_mode,
            target_ticker=target_ticker,
        )
        event_dir = save_event_trader_step(run_id, event_data)
        outputs["event"] = event_data
        dirs["event_dir"] = event_dir
        _notify_step(step_callback, "event", event_data, event_dir)
    except Exception as exc:
        error = _error_payload("event", exc)
        _notify_step(step_callback, "event", status="failed", error=error["message"])
        return {"outputs": outputs, "dirs": dirs, "status": "failed", "error": error}

    try:
        print("STEP 8: Validator...")
        validator_data = await run_validator(
            research_data,
            value_data,
            growth_data,
            macro_data,
            event_data,
            run_id,
        )
        validator_dir = save_validator_step(run_id, validator_data)
        outputs["validator"] = validator_data
        dirs["validator_dir"] = validator_dir
        _notify_step(step_callback, "validator", validator_data, validator_dir)
    except Exception as exc:
        error = _error_payload("validator", exc)
        _notify_step(step_callback, "validator", status="failed", error=error["message"])
        return {"outputs": outputs, "dirs": dirs, "status": "failed", "error": error}

    return {
        "outputs": outputs,
        "dirs": dirs,
        "status": "completed",
        "error": None,
    }


async def run_full_workflow(run_id: str, client, step_callback: StepCallback | None = None) -> dict[str, object]:
    outputs: dict[str, object] = {}
    dirs: dict[str, object] = {}
    print("STEP 1: Collect raw data...")
    research_input, research_source_availability = build_research_input()

    try:
        print("STEP 2: Extract signals...")
        signal_data = await run_signal_extractor(research_input, run_id, client)
        signal_data["data_availability"] = research_source_availability

        print("STEP 3: Generate sector ideas...")
        research_data = await run_research_from_signals(signal_data, run_id, client)

        print("STEP 3.25: Discover candidate stocks...")
        discovery_data = await run_candidate_discovery(research_data, run_id, client)
        research_data = enrich_research_data_with_discovery(research_data, discovery_data)
        research_dir = save_research_step(run_id, research_data)
        outputs["research"] = research_data
        dirs["research_dir"] = research_dir
        _notify_step(step_callback, "research", research_data, research_dir)

        print("STEP 3.5: Build shared evidence pack...")
        trader_universe = build_stock_universe_for_trader_pool(research_data)
        shared_ticker_cache: dict[str, dict[str, object]] = {}
        shared_evidence_pack = build_evidence_pack(
            trader_universe,
            ticker_cache=shared_ticker_cache,
        )
    except Exception as exc:
        error = _error_payload("research", exc)
        _notify_step(step_callback, "research", data=outputs.get("research", {}), status="failed", error=error["message"])
        return {
            "run_id": run_id,
            "mode": "whole_procedure",
            "outputs": outputs,
            "dirs": dirs,
            "status": "failed",
            "error": error,
        }

    downstream = await _run_trader_and_validator_steps(
        run_id,
        research_data,
        shared_evidence_pack,
        step_callback=step_callback,
    )

    return {
        "run_id": run_id,
        "mode": "whole_procedure",
        "outputs": downstream["outputs"],
        "dirs": {
            **dirs,
            **downstream["dirs"],
        },
        "status": downstream.get("status", "completed"),
        "error": downstream.get("error"),
    }


async def run_industry_workflow(run_id: str, client, industry: str, step_callback: StepCallback | None = None) -> dict[str, object]:
    outputs: dict[str, object] = {}
    dirs: dict[str, object] = {}
    print("STEP 1: Collect industry raw data...")
    research_input, research_source_availability = build_industry_research_input(industry)

    try:
        print("STEP 2: Extract industry signals...")
        signal_data = await run_signal_extractor(research_input, run_id, client)
        signal_data["data_availability"] = research_source_availability

        print("STEP 3: Generate industry sector ideas...")
        research_data = await run_research_from_signals(signal_data, run_id, client)
        print("STEP 3.25: Discover candidate stocks...")
        discovery_data = await run_candidate_discovery(research_data, run_id, client)
        research_data = enrich_research_data_with_discovery(research_data, discovery_data)
        research_data["user_selected_industry"] = industry.strip()
        research_dir = save_research_step(run_id, research_data)
        outputs["research"] = research_data
        dirs["research_dir"] = research_dir
        _notify_step(step_callback, "research", research_data, research_dir)

        print("STEP 3.5: Build shared evidence pack...")
        trader_universe = build_stock_universe_for_trader_pool(research_data)
        shared_ticker_cache: dict[str, dict[str, object]] = {}
        shared_evidence_pack = build_evidence_pack(
            trader_universe,
            ticker_cache=shared_ticker_cache,
        )
    except Exception as exc:
        error = _error_payload("research", exc)
        _notify_step(step_callback, "research", data=outputs.get("research", {}), status="failed", error=error["message"])
        return {
            "run_id": run_id,
            "mode": "industry",
            "input_label": industry.strip(),
            "outputs": outputs,
            "dirs": dirs,
            "status": "failed",
            "error": error,
        }

    downstream = await _run_trader_and_validator_steps(
        run_id,
        research_data,
        shared_evidence_pack,
        step_callback=step_callback,
    )

    return {
        "run_id": run_id,
        "mode": "industry",
        "input_label": industry.strip(),
        "outputs": downstream["outputs"],
        "dirs": {
            **dirs,
            **downstream["dirs"],
        },
        "status": downstream.get("status", "completed"),
        "error": downstream.get("error"),
    }


async def run_stock_workflow(run_id: str, client, ticker: str, step_callback: StepCallback | None = None) -> dict[str, object]:
    tickers = parse_ticker_list(ticker)
    if not tickers:
        return {
            "run_id": run_id,
            "mode": "stock",
            "input_label": "",
            "outputs": {},
            "dirs": {},
            "status": "failed",
            "error": {"step": "research", "message": "No valid ticker input provided."},
        }

    if len(tickers) > 1:
        batch_outputs: dict[str, Any] = {}
        batch_dirs: dict[str, Any] = {}
        batch_status = "completed"
        batch_error: dict[str, str] | None = None

        for single_ticker in tickers:
            sub_run_id = f"{run_id}__{single_ticker}"
            sub_result = await run_stock_workflow(sub_run_id, client, single_ticker)
            batch_outputs[single_ticker] = sub_result
            batch_dirs[single_ticker] = sub_result.get("dirs", {})
            if step_callback is not None:
                step_callback(
                    f"batch:{single_ticker}",
                    {
                        "status": sub_result.get("status", "completed"),
                        "data": sub_result,
                    },
                )
            if sub_result.get("status") != "completed" and batch_status == "completed":
                batch_status = "failed"
                batch_error = sub_result.get("error")

        return {
            "run_id": run_id,
            "mode": "stock_batch",
            "input_label": ", ".join(tickers),
            "outputs": {
                "batch": batch_outputs,
            },
            "dirs": {
                "batch": batch_dirs,
            },
            "status": batch_status,
            "error": batch_error,
        }

    normalized_ticker = tickers[0]
    print("STEP 1: Build direct stock context...")
    try:
        research_data, shared_evidence_pack = build_single_stock_context(normalized_ticker, run_id)
        _notify_step(step_callback, "research", research_data)
    except Exception as exc:
        error = _error_payload("research", exc)
        _notify_step(step_callback, "research", status="failed", error=error["message"])
        return {
            "run_id": run_id,
            "mode": "stock",
            "input_label": normalized_ticker,
            "outputs": {},
            "dirs": {},
            "status": "failed",
            "error": error,
        }

    downstream = await _run_trader_and_validator_steps(
        run_id,
        research_data,
        shared_evidence_pack,
        analysis_mode="single_stock",
        target_ticker=normalized_ticker,
        step_callback=step_callback,
    )

    return {
        "run_id": run_id,
        "mode": "stock",
        "input_label": normalized_ticker,
        "outputs": downstream["outputs"],
        "dirs": downstream["dirs"],
        "status": downstream.get("status", "completed"),
        "error": downstream.get("error"),
    }


async def run_research_and_four_traders(run_id: str, client) -> dict[str, Path]:
    result = await run_full_workflow(run_id=run_id, client=client)
    return result["dirs"]
