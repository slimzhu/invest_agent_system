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


def _run_workflow(kind: str, value: str | None = None) -> dict[str, Any]:
    ensure_api_key()
    client = configure_client()
    run_id = create_run_id()

    if kind == "whole":
        return _run_async(run_full_workflow(run_id=run_id, client=client))
    if kind == "industry":
        return _run_async(run_industry_workflow(run_id=run_id, client=client, industry=value or ""))
    if kind == "stock":
        return _run_async(run_stock_workflow(run_id=run_id, client=client, ticker=value or ""))
    raise ValueError(f"Unsupported workflow kind: {kind}")


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
    st.success(f"Run completed: {result.get('run_id', '')}")

    meta_cols = st.columns(3)
    meta_cols[0].metric("Mode", result.get("mode", ""))
    meta_cols[1].metric("Run ID", result.get("run_id", ""))
    meta_cols[2].metric("Input", result.get("input_label", "Whole Procedure"))

    outputs = result.get("outputs", {})

    if "research" in outputs and result.get("mode") != "stock":
        _show_step(
            "01 Researcher",
            generate_research_markdown(outputs["research"]),
            outputs["research"],
        )
    elif "research" in outputs and result.get("mode") == "stock":
        with st.expander("01 Direct Stock Context", expanded=True):
            st.json(outputs["research"])

    _show_step(
        "02 Value Trader",
        generate_trader_markdown("# 💰 Value Trader Report", outputs["value"]),
        outputs["value"],
    )
    _show_step(
        "03 Growth Trader",
        generate_trader_markdown("# 🚀 Growth Trader Report", outputs["growth"]),
        outputs["growth"],
    )
    _show_step(
        "04 Macro Trader",
        generate_trader_markdown("# 🌍 Macro Trader Report", outputs["macro"]),
        outputs["macro"],
    )
    _show_step(
        "05 Event Trader",
        generate_trader_markdown("# ⚡ Event Trader Report", outputs["event"]),
        outputs["event"],
    )
    _show_step(
        "06 Validator",
        generate_validator_markdown(outputs["validator"]),
        outputs["validator"],
    )

    with st.expander("Saved Paths", expanded=False):
        st.json(result.get("dirs", {}))


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
            st.session_state.workflow_result = _run_workflow("whole")

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
                st.session_state.workflow_result = _run_workflow("industry", industry.strip())

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
                st.session_state.workflow_result = _run_workflow("stock", ticker.strip().upper())

result = st.session_state.get("workflow_result")
if result:
    st.divider()
    _render_workflow_result(result)
