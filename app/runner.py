from pathlib import Path
import json

from app.agents.research_agent import run_research_from_signals
from app.agents.research_signal_agent import run_signal_extractor
from app.agents.trader_value_agent import run_value_trader
from app.agents.trader_growth_agent import run_growth_trader
from app.agents.trader_macro_agent import run_macro_trader
from app.agents.trader_event_agent import run_event_trader
from app.agents.validator_agent import run_validator
from app.tools.evidence_pack_builder import build_evidence_pack
from app.tools.universe_builder import build_stock_universe_for_trader_pool
from app.sources.research_sources import (
    get_brave_search_results,
    get_finnhub_company_news,
    get_finnhub_market_news,
    get_sec_company_facts,
    get_sec_company_submissions,
)
from app.storage import (
    save_research_step,
    save_value_trader_step,
    save_growth_trader_step,
    save_macro_trader_step,
    save_event_trader_step,
    save_validator_step,
)


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
            "Broadly scan U.S. equity sectors/themes and identify 8 to 12 candidates first, "
            "then narrow them to the best 3 non-consensus, alpha-oriented opportunities over the next 3 to 12 months."
        ),
    }

    return (
        json.dumps(source_bundle, ensure_ascii=False, indent=2),
        summarize_research_source_bundle(source_bundle),
    )


async def run_research_and_four_traders(run_id: str, client) -> dict[str, Path]:
    print("STEP 1: Collect raw data...")
    research_input, research_source_availability = build_research_input()

    print("STEP 2: Extract signals...")
    signal_data = await run_signal_extractor(research_input, run_id, client)
    signal_data["data_availability"] = research_source_availability

    print("STEP 3: Generate sector ideas...")
    research_data = await run_research_from_signals(signal_data, run_id, client)
    research_dir = save_research_step(run_id, research_data)

    print("STEP 3.5: Build shared evidence pack...")
    trader_universe = build_stock_universe_for_trader_pool(research_data)
    shared_ticker_cache: dict[str, dict[str, object]] = {}
    shared_evidence_pack = build_evidence_pack(
        trader_universe,
        ticker_cache=shared_ticker_cache,
    )

    print("STEP 4: Value trader...")
    value_data = await run_value_trader(
        research_data,
        run_id,
        shared_evidence_pack=shared_evidence_pack,
    )
    value_dir = save_value_trader_step(run_id, value_data)

    print("STEP 5: Growth trader...")
    growth_data = await run_growth_trader(
        research_data,
        run_id,
        shared_evidence_pack=shared_evidence_pack,
    )
    growth_dir = save_growth_trader_step(run_id, growth_data)

    print("STEP 6: Macro trader...")
    macro_data = await run_macro_trader(
        research_data,
        run_id,
        shared_evidence_pack=shared_evidence_pack,
    )
    macro_dir = save_macro_trader_step(run_id, macro_data)

    print("STEP 7: Event trader...")
    event_data = await run_event_trader(
        research_data,
        run_id,
        shared_evidence_pack=shared_evidence_pack,
    )
    event_dir = save_event_trader_step(run_id, event_data)

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

    return {
        "research_dir": research_dir,
        "value_dir": value_dir,
        "growth_dir": growth_dir,
        "macro_dir": macro_dir,
        "event_dir": event_dir,
        "validator_dir": validator_dir,
    }
