from __future__ import annotations

import asyncio
import json
from typing import Any

import streamlit as st

from app.runner import run_full_workflow, run_industry_workflow, run_stock_workflow
from app.runtime import configure_client, ensure_api_key
from app.storage import (
    create_run_id,
    generate_research_markdown,
    generate_trader_markdown,
    generate_validator_markdown,
)


st.set_page_config(
    page_title="Investment Agent System",
    layout="wide",
)


def _run_async(coro):
    return asyncio.run(coro)


def _build_live_result(kind: str, run_id: str, value: str | None = None) -> dict[str, Any]:
    mode = {
        "whole": "whole_procedure",
        "industry": "industry",
        "stock": "stock",
    }.get(kind, kind)
    result = {
        "run_id": run_id,
        "mode": mode,
        "input_label": value or ("Whole Procedure" if kind == "whole" else ""),
        "outputs": {},
        "dirs": {},
        "status": "running",
        "error": None,
    }
    return result


def _run_workflow(
    kind: str,
    value: str | None = None,
    run_id: str | None = None,
    step_callback=None,
) -> dict[str, Any]:
    ensure_api_key()
    client = configure_client()
    run_id = run_id or create_run_id()

    if kind == "whole":
        return _run_async(run_full_workflow(run_id=run_id, client=client, step_callback=step_callback))
    if kind == "industry":
        return _run_async(
            run_industry_workflow(
                run_id=run_id,
                client=client,
                industry=value or "",
                step_callback=step_callback,
            )
        )
    if kind == "stock":
        return _run_async(
            run_stock_workflow(
                run_id=run_id,
                client=client,
                ticker=value or "",
                step_callback=step_callback,
            )
        )
    raise ValueError(f"Unsupported workflow kind: {kind}")


def _render_final_combined_summary(result: dict[str, Any]) -> None:
    outputs = result.get("outputs", {})
    validator = outputs.get("validator", {})
    error = result.get("error") or {}
    status = result.get("status", "completed")

    st.subheader("Final Combined Summary")
    if status == "completed":
        st.success("Workflow completed successfully.")
    elif outputs:
        st.warning("Workflow completed partially. Earlier completed steps are shown below.")
    else:
        st.error("Workflow failed before producing usable outputs.")

    if error:
        st.error(f"Stopped at `{error.get('step', 'unknown')}`: {error.get('message', 'Unknown error')}")

    meta_cols = st.columns(4)
    meta_cols[0].metric("Mode", result.get("mode", ""))
    meta_cols[1].metric("Run ID", result.get("run_id", ""))
    meta_cols[2].metric("Completed Steps", len(outputs))
    meta_cols[3].metric("Input", result.get("input_label", "Whole Procedure"))

    if validator:
        st.markdown(f"**Overall Decision:** `{validator.get('overall_decision', 'N/A')}`")
        if validator.get("portfolio_verdict"):
            st.markdown(f"**Portfolio Verdict:** {validator.get('portfolio_verdict')}")
        observations = validator.get("cross_trader_observations", [])
        if observations:
            st.markdown("**Cross-Trader Notes**")
            for item in observations[:5]:
                st.markdown(f"- {item}")
    else:
        selected_summary: list[str] = []
        for key in ("value", "growth", "macro", "event"):
            trader = outputs.get(key, {})
            picks = trader.get("selected_stocks", [])
            tickers = [item.get("ticker", "") for item in picks if isinstance(item, dict) and item.get("ticker")]
            if tickers:
                selected_summary.append(f"`{key}`: {', '.join(tickers)}")
        if selected_summary:
            st.markdown("**Completed Trader Outputs**")
            for item in selected_summary:
                st.markdown(f"- {item}")
    if result.get("mode") == "stock_batch":
        batch = outputs.get("batch", {})
        completed = sum(1 for item in batch.values() if isinstance(item, dict) and item.get("status") == "completed")
        st.markdown(f"**Batch Stocks Completed:** {completed}/{len(batch)}")


def _show_step(title: str, markdown_text: str, data: dict[str, Any]) -> None:
    with st.expander(title, expanded=True):
        tab_md, tab_json, tab_raw = st.tabs(["Report", "JSON", "Raw Output"])
        with tab_md:
            st.markdown(markdown_text)
        with tab_json:
            st.json(data)
        with tab_raw:
            raw_output = data.get("raw_output")
            if raw_output:
                st.code(raw_output, language="json")
            else:
                st.caption("No raw_output recorded for this step.")


def _render_workflow_result(result: dict[str, Any]) -> None:
    _render_final_combined_summary(result)

    outputs = result.get("outputs", {})

    if result.get("mode") == "stock_batch":
        batch_outputs = outputs.get("batch", {})
        for ticker, ticker_result in batch_outputs.items():
            if not isinstance(ticker_result, dict):
                continue
            st.divider()
            st.subheader(f"Stock Batch: {ticker}")
            _render_workflow_result(ticker_result)
        with st.expander("Saved Paths", expanded=False):
            st.json(result.get("dirs", {}))
        return

    if "research" in outputs and result.get("mode") != "stock":
        _show_step(
            "01 Researcher",
            generate_research_markdown(outputs["research"]),
            outputs["research"],
        )
    elif "research" in outputs and result.get("mode") == "stock":
        with st.expander("01 Direct Stock Context", expanded=True):
            st.json(outputs["research"])

    if "value" in outputs:
        _show_step(
            "02 Value Trader",
            generate_trader_markdown("# 💰 Value Trader Report", outputs["value"]),
            outputs["value"],
        )
    if "growth" in outputs:
        _show_step(
            "03 Growth Trader",
            generate_trader_markdown("# 🚀 Growth Trader Report", outputs["growth"]),
            outputs["growth"],
        )
    if "macro" in outputs:
        _show_step(
            "04 Macro Trader",
            generate_trader_markdown("# 🌍 Macro Trader Report", outputs["macro"]),
            outputs["macro"],
        )
    if "event" in outputs:
        _show_step(
            "05 Event Trader",
            generate_trader_markdown("# ⚡ Event Trader Report", outputs["event"]),
            outputs["event"],
        )
    if "validator" in outputs:
        _show_step(
            "06 Validator",
            generate_validator_markdown(outputs["validator"]),
            outputs["validator"],
        )

    with st.expander("Saved Paths", expanded=False):
        st.json(result.get("dirs", {}))


def _run_with_live_render(kind: str, value: str | None = None) -> dict[str, Any]:
    run_id = create_run_id()
    live_result: dict[str, Any] = _build_live_result(kind, run_id, value)
    render_placeholder = st.empty()

    def _refresh() -> None:
        with render_placeholder.container():
            _render_workflow_result(live_result)

    def _step_callback(step_key: str, payload: dict[str, Any]) -> None:
        if step_key.startswith("batch:"):
            ticker = step_key.split(":", 1)[1]
            batch = live_result["outputs"].setdefault("batch", {})
            batch[ticker] = payload.get("data", {})
            if payload.get("status") == "failed":
                live_result["status"] = "failed"
                live_result["error"] = {
                    "step": step_key,
                    "message": payload.get("error", "Unknown step error"),
                }
            _refresh()
            return
        if payload.get("data"):
            live_result["outputs"][step_key] = payload["data"]
        if payload.get("dir"):
            live_result["dirs"][f"{step_key}_dir"] = payload["dir"]
        if payload.get("status") == "failed":
            live_result["status"] = "failed"
            live_result["error"] = {
                "step": step_key,
                "message": payload.get("error", "Unknown step error"),
            }
        _refresh()

    _refresh()

    result = _run_workflow(kind, value, run_id=run_id, step_callback=_step_callback)
    result_outputs = result.get("outputs", {})
    result_dirs = result.get("dirs", {})
    live_result["run_id"] = result.get("run_id", live_result["run_id"])
    live_result["mode"] = result.get("mode", live_result["mode"])
    live_result["input_label"] = result.get("input_label", live_result["input_label"])
    live_result["outputs"] = result_outputs
    live_result["dirs"] = result_dirs
    live_result["status"] = result.get("status", "completed")
    live_result["error"] = result.get("error")
    _refresh()
    render_placeholder.empty()
    return live_result


st.title("Investment Agent System")
st.caption("Run the full workflow, analyze a user-selected industry, or analyze a single stock and inspect every agent output.")

if "workflow_result" not in st.session_state:
    st.session_state.workflow_result = None

col1, col2 = st.columns([1.2, 1])

with col1:
    st.subheader("Run whole procedure")
    st.write("Use the existing end-to-end pipeline: researcher -> four traders -> validator.")
    if st.button("Run whole procedure", type="primary", use_container_width=True):
        with st.spinner("Running whole procedure..."):
            st.session_state.workflow_result = _run_with_live_render("whole")

    st.subheader("Analyze an industry")
    industry = st.text_input(
        "Industry / theme",
        placeholder="e.g. semiconductor equipment, data center cooling, power grid",
    )
    if st.button("Run industry workflow", use_container_width=True):
        if not industry.strip():
            st.warning("Please enter an industry or theme first.")
        else:
            with st.spinner(f"Running industry workflow for {industry.strip()}..."):
                st.session_state.workflow_result = _run_with_live_render("industry", industry.strip())

with col2:
    st.subheader("Analyze a single stock")
    ticker = st.text_input(
        "Ticker",
        placeholder="e.g. MU, ANET, ETN",
    )
    if st.button("Run stock workflow", use_container_width=True):
        if not ticker.strip():
            st.warning("Please enter a ticker first.")
        else:
            with st.spinner(f"Running stock workflow for {ticker.strip().upper()}..."):
                st.session_state.workflow_result = _run_with_live_render("stock", ticker.strip().upper())

result = st.session_state.get("workflow_result")
if result:
    st.divider()
    _render_workflow_result(result)
