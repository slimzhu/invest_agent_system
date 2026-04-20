import json
from datetime import datetime
from pathlib import Path
from typing import Any


BASE_DIR = Path(__file__).resolve().parent
RUNS_DIR = BASE_DIR / "data" / "runs"


def create_run_id() -> str:
    return datetime.now().strftime("%Y-%m-%d_%H%M%S")


def create_run_dir(run_id: str) -> Path:
    run_dir = RUNS_DIR / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


def create_step_dir(run_id: str, step_name: str) -> Path:
    run_dir = create_run_dir(run_id)
    step_dir = run_dir / step_name
    step_dir.mkdir(parents=True, exist_ok=True)
    return step_dir


def save_json(file_path: Path, data: dict[str, Any]) -> None:
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def save_text(file_path: Path, content: str) -> None:
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)

import json
from typing import Any


def _append_list_or_text(lines: list[str], value: Any, empty_text: str = "- N/A") -> None:
    if isinstance(value, list):
        if value:
            for item in value:
                lines.append(f"- {item}")
        else:
            lines.append(empty_text)
        return

    if isinstance(value, str):
        text = value.strip()
        lines.append(text if text else empty_text)
        return

    if value:
        lines.append(str(value))
    else:
        lines.append(empty_text)


def _append_timeline_dict(lines: list[str], value: Any) -> None:
    if isinstance(value, dict):
        if not value:
            lines.append("- N/A")
            return

        label_map = {
            "short_term": "Short Term",
            "medium_term": "Medium Term",
            "long_term": "Long Term",
        }
        for key in ("short_term", "medium_term", "long_term"):
            if key not in value:
                continue
            lines.append(f"- {label_map.get(key, key)}:")
            subvalue = value.get(key, [])
            if isinstance(subvalue, list) and subvalue:
                for item in subvalue:
                    lines.append(f"  - {item}")
            elif isinstance(subvalue, str) and subvalue.strip():
                lines.append(f"  - {subvalue.strip()}")
            else:
                lines.append("  - N/A")
        return

    _append_list_or_text(lines, value)


def _append_data_availability(lines: list[str], data_availability: dict[str, Any]) -> None:
    if not data_availability:
        return

    lines.append("## 📡 Data Availability")
    lines.append("")

    overall = data_availability.get("overall")
    if isinstance(overall, dict):
        companies = overall.get("companies")
        if companies is not None:
            lines.append(f"**Companies Covered:** {companies}")
            lines.append("")

        sources = overall.get("sources", {})
        if isinstance(sources, dict) and sources:
            lines.append("**Source Coverage**")
            for source_name, stats in sources.items():
                if not isinstance(stats, dict):
                    continue
                available = stats.get("available", 0)
                missing = stats.get("missing", 0)
                lines.append(f"- `{source_name}`: available={available}, missing={missing}")
            lines.append("")

    for group_name, summary in data_availability.items():
        if group_name == "overall" or not isinstance(summary, dict):
            continue

        if any(key in summary for key in ("total", "available", "missing")):
            lines.append(f"### {group_name}")
            lines.append("")
            total = summary.get("total")
            available = summary.get("available")
            missing = summary.get("missing")
            item_count = summary.get("item_count")
            lines.append(
                f"- total={total}, available={available}, missing={missing}, items={item_count}"
            )
            sample_errors = summary.get("sample_errors", [])
            for err in sample_errors[:2]:
                lines.append(f"- sample error: {err}")
            lines.append("")
            continue

        if any(key in summary for key in ("enabled", "item_count", "error")):
            lines.append(f"### {group_name}")
            lines.append("")
            enabled = summary.get("enabled")
            item_count = summary.get("item_count", 0)
            error = summary.get("error")
            detail = f"enabled={enabled}, items={item_count}"
            if error:
                detail += f", error={error}"
            lines.append(f"- {detail}")
            lines.append("")
            continue

        if "company_count" in summary:
            lines.append(f"### {group_name}")
            lines.append("")
            for company in summary.get("companies", []):
                ticker = company.get("ticker", "N/A")
                lines.append(f"**{ticker}**")
                for source_name, source_summary in company.get("sources", {}).items():
                    enabled = source_summary.get("enabled", False)
                    item_count = source_summary.get("item_count", 0)
                    error = source_summary.get("error")
                    status = "ok" if enabled else "missing"
                    detail = f"{status}, items={item_count}"
                    if error:
                        detail += f", error={error}"
                    lines.append(f"- `{source_name}`: {detail}")
                lines.append("")
            continue

        lines.append(f"### {group_name}")
        lines.append("")
        for key, value in summary.items():
            if isinstance(value, dict):
                enabled = value.get("enabled")
                if enabled is not None:
                    detail = f"enabled={enabled}, items={value.get('item_count', 0)}"
                    error = value.get("error")
                    if error:
                        detail += f", error={error}"
                    lines.append(f"- `{key}`: {detail}")
                else:
                    total = value.get("total")
                    available = value.get("available")
                    missing = value.get("missing")
                    item_count = value.get("item_count")
                    lines.append(
                        f"- `{key}`: total={total}, available={available}, missing={missing}, items={item_count}"
                    )
                    sample_errors = value.get("sample_errors", [])
                    for err in sample_errors[:2]:
                        lines.append(f"- `{key}` sample error: {err}")
        lines.append("")


def _append_plan_dict(lines: list[str], title: str, value: Any) -> None:
    lines.append(f"**{title}**")
    if isinstance(value, dict) and value:
        for key, item in value.items():
            label = key.replace("_", " ").strip().title()
            if isinstance(item, list):
                if item:
                    lines.append(f"- {label}:")
                    for sub_item in item:
                        lines.append(f"  - {sub_item}")
                else:
                    lines.append(f"- {label}: N/A")
            elif item not in (None, "", {}, []):
                lines.append(f"- {label}: {item}")
        if not any(item not in (None, "", {}, []) for item in value.values()):
            lines.append("- N/A")
    elif isinstance(value, str) and value.strip():
        lines.append(value.strip())
    else:
        lines.append("- N/A")
    lines.append("")

def generate_research_markdown(data: dict[str, Any]) -> str:
    run_id = data.get("run_id", "")
    created_at = data.get("created_at", "")
    model = data.get("model", "")
    signal_input = data.get("signal_input", {})
    candidate_sectors = data.get("candidate_sectors", [])
    final_sectors = data.get("final_sectors", [])
    summary = data.get("summary", "")
    data_availability = signal_input.get("data_availability", {})
    discovery_output = data.get("candidate_discovery", {})

    lines: list[str] = []
    lines.append("# 📊 Market Research Report")
    lines.append(f"**Run ID:** {run_id}  ")
    lines.append(f"**Created At:** {created_at}  ")
    lines.append(f"**Model:** {model}")
    lines.append("")
    lines.append("---")
    lines.append("")

    lines.append("## 🔬 Signal Snapshot")
    lines.append("")
    if signal_input:
        pretty_signal = json.dumps(signal_input, ensure_ascii=False, indent=2)
        lines.append("```json")
        lines.append(pretty_signal[:12000])
        lines.append("```")
    else:
        lines.append("No signal snapshot recorded.")
    lines.append("")
    lines.append("---")
    lines.append("")

    _append_data_availability(lines, data_availability)
    lines.append("---")
    lines.append("")

    if isinstance(discovery_output, dict) and discovery_output.get("theme_candidates"):
        lines.append("## 🧩 Candidate Discovery")
        lines.append("")
        for item in discovery_output.get("theme_candidates", []):
            if not isinstance(item, dict):
                continue
            lines.append(f"### {item.get('theme', 'Unknown Theme')}")
            lines.append("")
            seed = item.get("seed_tickers", [])
            validated = item.get("validated_tickers", [])
            lines.append(f"**Seed Tickers:** {', '.join(seed) if seed else 'N/A'}")
            lines.append("")
            lines.append(f"**Validated Additions:** {', '.join(validated) if validated else 'None'}")
            lines.append("")
            lines.append("**Rationale**")
            lines.append(item.get("rationale", ""))
            lines.append("")
        lines.append("---")
        lines.append("")

    lines.append("## 🧭 Candidate Sectors")
    lines.append("")
    if not candidate_sectors:
        lines.append("No candidate sectors generated.")
        lines.append("")
    else:
        for idx, item in enumerate(candidate_sectors, start=1):
            lines.append(f"### {idx}. {item.get('name', 'Unknown')}")
            lines.append("")
            lines.append(f"**Decision:** {item.get('decision', 'N/A')}")
            lines.append("")
            lines.append("**Reason**")
            lines.append(item.get("reason", ""))
            lines.append("")
            lines.append("---")
            lines.append("")

    lines.append("## 🎯 Final Sectors")
    lines.append("")
    if not final_sectors:
        lines.append("No final sectors generated.")
        lines.append("")
    else:
        for idx, sector in enumerate(final_sectors, start=1):
            lines.append(f"### {idx}. {sector.get('name', 'Unknown')}")
            lines.append("")
            lines.append(f"**Conviction:** {sector.get('conviction', 'N/A')}")
            lines.append("")
            lines.append("**Thesis**")
            lines.append(sector.get("thesis", ""))
            lines.append("")
            lines.append("**Why Now**")
            lines.append(sector.get("why_now", ""))
            lines.append("")

            lines.append("**Drivers**")
            _append_timeline_dict(lines, sector.get("drivers", []))
            lines.append("")

            lines.append("**Risks**")
            _append_timeline_dict(lines, sector.get("risks", []))
            lines.append("")

            lines.append("**Positioning**")
            lines.append(sector.get("positioning", ""))
            lines.append("")
            lines.append("**Catalyst**")
            lines.append(sector.get("catalyst", ""))
            lines.append("")
            lines.append("---")
            lines.append("")

    lines.append("## 📌 Summary")
    lines.append(summary if summary else "No summary generated.")
    lines.append("")

    return "\n".join(lines)


def generate_trader_markdown(
    title: str,
    data: dict[str, Any],
    fit_label: str | None = None,
    signal_label: str | None = None,
) -> str:
    run_id = data.get("run_id", "")
    created_at = data.get("created_at", "")
    model = data.get("model", "")
    decision = data.get("decision", "")
    style = data.get("style", "")
    sector_review_decision = data.get("sector_review_decision", "")
    accepted_sectors = data.get("accepted_sectors", [])
    rejected_sectors = data.get("rejected_sectors", [])
    replacement_sectors = data.get("replacement_sectors", [])
    chosen_sectors = data.get("chosen_sectors", [])
    sector_review_reason = data.get("sector_review_reason", "")
    selected_stocks = data.get("selected_stocks", [])
    watch_stocks = data.get("watch_stocks", [])
    summary = data.get("summary", "")
    tool_calls = data.get("tool_calls", [])
    data_availability = data.get("data_availability", {})

    lines: list[str] = []
    lines.append(title)
    lines.append(f"**Run ID:** {run_id}  ")
    lines.append(f"**Created At:** {created_at}  ")
    lines.append(f"**Model:** {model}  ")
    lines.append(f"**Decision:** {decision}  ")
    lines.append(f"**Style:** {style}")
    lines.append("")
    lines.append("---")
    lines.append("")

    lines.append("## 🧭 Sector Review")
    lines.append("")
    lines.append(f"**Decision:** {sector_review_decision or 'N/A'}")
    lines.append("")
    lines.append(f"**Chosen Sectors:** {', '.join(chosen_sectors) if chosen_sectors else 'N/A'}")
    lines.append("")
    if accepted_sectors:
        lines.append(f"**Accepted Final Sectors:** {', '.join(accepted_sectors)}")
        lines.append("")
    if rejected_sectors:
        lines.append(f"**Rejected Final Sectors:** {', '.join(rejected_sectors)}")
        lines.append("")
    if replacement_sectors:
        lines.append(f"**Replacement Sectors:** {', '.join(replacement_sectors)}")
        lines.append("")
    lines.append("**Reason**")
    lines.append(sector_review_reason or "No sector review reason recorded.")
    lines.append("")
    lines.append("---")
    lines.append("")

    lines.append("## 🛠 Tool Calls")
    lines.append("")
    if not tool_calls:
        lines.append("No tool calls recorded.")
        lines.append("")
    else:
        for index, call in enumerate(tool_calls, start=1):
            lines.append(f"### Tool Call {index}")
            lines.append("")
            lines.append(f"**Tool:** {call.get('tool_name', 'N/A')}")
            lines.append(f"**Ticker:** {call.get('ticker', 'N/A')}")
            lines.append("")
            lines.append("---")
            lines.append("")

    lines.append("## 👀 Watch List")
    lines.append("")
    if not watch_stocks:
        lines.append("No watch stocks recorded.")
        lines.append("")
    else:
        for index, stock in enumerate(watch_stocks, start=1):
            lines.append(f"### {index}. {stock.get('ticker', 'N/A')} — {stock.get('company_name', 'N/A')}")
            lines.append("")
            lines.append(f"**Sector Theme:** {stock.get('sector_theme', 'N/A')}")
            lines.append("")
            lines.append("**Reason For Monitoring**")
            lines.append(stock.get("reason_for_monitoring", stock.get("reason", "")))
            lines.append("")
            lines.append("**Evidence Used**")
            evidence_used = stock.get("evidence_used", [])
            _append_list_or_text(lines, evidence_used)
            lines.append("")
            lines.append("---")
            lines.append("")

    _append_data_availability(lines, data_availability)
    lines.append("---")
    lines.append("")

    lines.append("## 🎯 Stock Decisions")
    lines.append("")
    if not selected_stocks:
        lines.append("No stocks selected.")
        lines.append("")
    else:
        for index, stock in enumerate(selected_stocks, start=1):
            lines.append(f"### {index}. {stock.get('ticker', 'N/A')} — {stock.get('company_name', 'N/A')}")
            lines.append("")
            lines.append(f"**Sector Theme:** {stock.get('sector_theme', 'N/A')}")
            lines.append(f"**Rating:** {stock.get('rating', 'N/A')}")
            lines.append(f"**Current Price:** {stock.get('current_price', 'N/A')}")
            lines.append(f"**Valuation View:** {stock.get('valuation_view', 'N/A')}")
            lines.append(f"**Confidence:** {stock.get('confidence', 'N/A')}")
            lines.append(f"**Conviction Score:** {stock.get('conviction_score', 'N/A')}")
            lines.append(f"**Time Horizon:** {stock.get('time_horizon', 'N/A')}")
            lines.append("")
            if fit_label:
                lines.append("**Style Fit**")
                lines.append(stock.get(fit_label, stock.get("why_this_stock", "")))
                lines.append("")
            lines.append("**Why This Stock**")
            lines.append(stock.get("why_this_stock", ""))
            lines.append("")
            lines.append("**Why Now**")
            lines.append(stock.get("why_now", ""))
            lines.append("")
            if signal_label:
                lines.append("**Style Signals**")
                style_signals = stock.get(signal_label, [])
                if style_signals:
                    for item in style_signals:
                        lines.append(f"- {item}")
                else:
                    lines.append("- N/A")
                lines.append("")
            lines.append("**Evidence Used**")
            evidence_used = stock.get("evidence_used", [])
            _append_list_or_text(lines, evidence_used)
            lines.append("")
            _append_plan_dict(lines, "Entry Strategy", stock.get("entry_strategy", {}))
            _append_plan_dict(lines, "Suggested Position Size", stock.get("position_sizing", {}))
            _append_plan_dict(lines, "Target Plan", stock.get("target_plan", {}))
            _append_plan_dict(lines, "Risk Plan", stock.get("risk_plan", {}))
            _append_plan_dict(lines, "Buy / Pass Triggers", stock.get("watch_conditions", {}))
            lines.append("**Upside Case**")
            lines.append(stock.get("upside_case", ""))
            lines.append("")
            lines.append("**Bear Case**")
            lines.append(stock.get("bear_case", ""))
            lines.append("")
            lines.append("**Key Risks**")
            _append_list_or_text(lines, stock.get("key_risks", []))
            lines.append("")
            lines.append("**Invalidation Conditions**")
            _append_list_or_text(lines, stock.get("invalidation_conditions", []))
            lines.append("")
            lines.append("---")
            lines.append("")

    lines.append("## 📌 Summary")
    lines.append(summary if summary else "No summary generated.")
    lines.append("")

    return "\n".join(lines)


def generate_validator_markdown(data: dict[str, Any]) -> str:
    run_id = data.get("run_id", "")
    created_at = data.get("created_at", "")
    model = data.get("model", "")
    overall_decision = data.get("overall_decision", "")
    portfolio_verdict = data.get("portfolio_verdict", "")
    validated_stocks = data.get("validated_stocks", [])
    trader_scorecards = data.get("trader_scorecards", [])
    cross_trader_observations = data.get("cross_trader_observations", [])
    summary = data.get("summary", "")

    lines: list[str] = []
    lines.append("# 🧪 Validator Report")
    lines.append(f"**Run ID:** {run_id}  ")
    lines.append(f"**Created At:** {created_at}  ")
    lines.append(f"**Model:** {model}  ")
    lines.append(f"**Overall Decision:** {overall_decision}")
    lines.append("")
    lines.append("---")
    lines.append("")

    lines.append("## 🧭 Portfolio Verdict")
    lines.append("")
    lines.append(portfolio_verdict if portfolio_verdict else "No portfolio verdict generated.")
    lines.append("")
    lines.append("---")
    lines.append("")

    lines.append("## 🧮 Trader Scorecards")
    lines.append("")
    if not trader_scorecards:
        lines.append("No trader scorecards returned.")
        lines.append("")
    else:
        for index, card in enumerate(trader_scorecards, start=1):
            lines.append(f"### {index}. {card.get('trader', 'N/A')}")
            lines.append("")
            lines.append(f"**Style:** {card.get('style', 'N/A')}")
            lines.append(f"**Decision Review:** {card.get('decision_review', 'N/A')}")
            lines.append(f"**Style Discipline:** {card.get('style_discipline', 'N/A')}")
            lines.append("")
            lines.append("**Sector Review Verdict**")
            lines.append(card.get("sector_review_verdict", ""))
            lines.append("")
            lines.append("**Portfolio Strengths**")
            _append_list_or_text(lines, card.get("portfolio_strengths", []))
            lines.append("")
            lines.append("**Portfolio Concerns**")
            _append_list_or_text(lines, card.get("portfolio_concerns", []))
            lines.append("")
            lines.append("---")
            lines.append("")

    lines.append("## 🔀 Cross-Trader Observations")
    lines.append("")
    _append_list_or_text(lines, cross_trader_observations, empty_text="No cross-trader observations returned.")
    lines.append("")
    lines.append("---")
    lines.append("")

    lines.append("## 🔍 Review Results")
    lines.append("")

    if not validated_stocks:
        lines.append("No validated stocks returned.")
        lines.append("")
    else:
        for index, stock in enumerate(validated_stocks, start=1):
            ticker = stock.get("ticker", "N/A")
            trader = stock.get("trader", "N/A")
            style = stock.get("style", "N/A")
            decision = stock.get("decision", "")
            verdict = stock.get("verdict", "")
            strengths = stock.get("strengths", [])
            concerns = stock.get("concerns", [])
            confidence_adjustment = stock.get("confidence_adjustment", "")
            sector_alignment = stock.get("sector_alignment", "")
            evidence_quality = stock.get("evidence_quality", "")

            lines.append(f"### {index}. {ticker} ({trader})")
            lines.append("")
            lines.append(f"**Style:** {style}")
            lines.append("")
            lines.append(f"**Decision:** {decision}")
            lines.append(f"**Evidence Quality:** {evidence_quality}")
            lines.append("")
            lines.append("**Verdict**")
            lines.append(verdict)
            lines.append("")
            lines.append("**Sector Alignment**")
            lines.append(sector_alignment if sector_alignment else "N/A")
            lines.append("")

            lines.append("**Strengths**")
            if strengths:
                for item in strengths:
                    lines.append(f"- {item}")
            else:
                lines.append("- N/A")
            lines.append("")

            lines.append("**Concerns**")
            if concerns:
                for item in concerns:
                    lines.append(f"- {item}")
            else:
                lines.append("- N/A")
            lines.append("")

            lines.append(f"**Confidence Adjustment:** {confidence_adjustment}")
            lines.append("")
            lines.append("---")
            lines.append("")

    lines.append("## 📌 Summary")
    lines.append(summary if summary else "No summary generated.")
    lines.append("")

    return "\n".join(lines)


def save_research_step(run_id: str, data: dict[str, Any]) -> Path:
    step_dir = create_step_dir(run_id, "01_researcher")
    save_json(step_dir / "data.json", data)
    save_text(step_dir / "report.md", generate_research_markdown(data))
    return step_dir


def save_value_trader_step(run_id: str, data: dict[str, Any]) -> Path:
    step_dir = create_step_dir(run_id, "02_trader_value")
    save_json(step_dir / "data.json", data)
    save_text(step_dir / "report.md", generate_trader_markdown("# 💰 Value Trader Report", data))
    return step_dir


def save_growth_trader_step(run_id: str, data: dict[str, Any]) -> Path:
    step_dir = create_step_dir(run_id, "03_trader_growth")
    save_json(step_dir / "data.json", data)
    save_text(step_dir / "report.md", generate_trader_markdown("# 🚀 Growth Trader Report", data))
    return step_dir


def save_macro_trader_step(run_id: str, data: dict[str, Any]) -> Path:
    step_dir = create_step_dir(run_id, "04_trader_macro")
    save_json(step_dir / "data.json", data)
    save_text(step_dir / "report.md", generate_trader_markdown("# 🌍 Macro Trader Report", data))
    return step_dir


def save_event_trader_step(run_id: str, data: dict[str, Any]) -> Path:
    step_dir = create_step_dir(run_id, "05_trader_event")
    save_json(step_dir / "data.json", data)
    save_text(step_dir / "report.md", generate_trader_markdown("# ⚡ Event Trader Report", data))
    return step_dir


def save_validator_step(run_id: str, data: dict[str, Any]) -> Path:
    step_dir = create_step_dir(run_id, "06_validator")
    save_json(step_dir / "data.json", data)
    save_text(step_dir / "report.md", generate_validator_markdown(data))
    return step_dir
