# Project Context

## One-line Summary

`invest_agent_system` is a Python multi-agent investment research workflow that collects live market/SEC/search data, produces sector theses, runs four style-specific trader agents, and then runs a validator over the combined portfolio outputs.

## Goal

The system is designed to simulate a buy-side idea generation process:

1. collect raw external signals
2. extract structured investment signals
3. generate candidate and final sectors
4. let multiple trader styles argue for stock picks
5. validate the final portfolio set with a second-pass reviewer

Primary output types:

- `BUY`
- `WATCH`
- `SELL`

## Current End-to-End Flow

Entrypoint:

- `app/main.py`

Orchestration:

- `app/runner.py`

Current runtime order:

1. `STEP 1`: collect raw data
2. `STEP 2`: signal extractor
3. `STEP 3`: researcher / sector strategist
4. `STEP 3.5`: build shared evidence pack
5. `STEP 4`: value trader
6. `STEP 5`: growth trader
7. `STEP 6`: macro trader
8. `STEP 7`: event trader
9. `STEP 8`: validator

## Agent Roles

### `research_signal_agent.py`

Turns noisy market/news/search/SEC input into structured signals.

Typical output:

- macro regime clues
- theme signals
- social / thematic signals
- noise separation

### `research_agent.py`

Acts as sector strategist.

Typical output:

- `candidate_sectors`
- `final_sectors`
- `summary`

### `trader_value_agent.py`

Looks for value / quality expressions inside approved sectors.

### `trader_growth_agent.py`

Looks for growth / innovation expressions inside approved sectors.

### `trader_macro_agent.py`

Looks for macro / capex / regime expressions inside approved sectors.

### `trader_event_agent.py`

Looks for catalyst-driven expressions inside approved sectors.

### `validator_agent.py`

Reviews all four trader portfolios together.

Current validator responsibilities:

- review each selected stock
- review each trader’s style discipline
- comment on cross-trader overlap
- downgrade incomplete or weakly justified portfolios

## Data Philosophy

This project should use **live data paths**, not mock data, in normal operation.

Important principle:

- trader agents are not information collectors
- trader agents are investment underwriters / thesis builders

So trader reasoning should be grounded in:

- 10-K / 10-Q / 8-K / DEF 14A when available
- filing analysis excerpts
- IR presentation / transcript / webcast links
- structured fundamentals
- valuation and market data
- recent company-specific news
- near-term and medium-term catalysts

## Main Data Sources

### SEC

Used for:

- company submissions
- company facts
- recent filings
- filing analysis

### Finnhub

Used for:

- quote
- basic financial metrics
- company profile
- market news
- company news

### Brave Search

Used for:

- thematic search
- social / idea sourcing
- IR / transcript / investor materials discovery

## Shared Evidence Pack

The system now builds a shared evidence pack before the traders run, so the four traders do not each re-fetch the same external data from scratch.

Relevant files:

- `app/tools/evidence_pack_builder.py`
- `app/tools/evidence_compactor.py`
- `app/tools/universe_builder.py`

Typical evidence pack contents per ticker:

- company profile
- market snapshot
- recent company news
- recent filings
- filing analysis
- structured fundamentals
- IR / transcript links

## Current Output Layout

Run outputs are stored under:

- `app/data/runs/<run_id>/01_researcher`
- `app/data/runs/<run_id>/02_trader_value`
- `app/data/runs/<run_id>/03_trader_growth`
- `app/data/runs/<run_id>/04_trader_macro`
- `app/data/runs/<run_id>/05_trader_event`
- `app/data/runs/<run_id>/06_validator`

Each step usually contains:

- `data.json`
- `report.md`

## Important Files

- `app/main.py`
- `app/runner.py`
- `app/config.py`
- `app/storage.py`
- `app/agents/*.py`
- `app/prompts/*.py`
- `app/sources/*.py`
- `app/tools/*.py`
- `app/utils/*.py`

## Configuration

Main configuration lives in:

- `app/config.py`
- `.env`
- `.env.example`

Important env vars:

- `OPENROUTER_API_KEY`
- `OPENROUTER_BASE_URL`
- `RESEARCH_MODEL`
- `VALUE_TRADER_MODEL`
- `GROWTH_TRADER_MODEL`
- `MACRO_TRADER_MODEL`
- `EVENT_TRADER_MODEL`
- `VALIDATOR_MODEL`
- `FINNHUB_API_KEY`
- `BRAVE_API_KEY`
- `POLYGON_API_KEY`
- `SEC_USER_AGENT`
- `RESEARCH_SOURCE_ENABLE_FINNHUB`
- `RESEARCH_SOURCE_ENABLE_BRAVE`
- `RESEARCH_SOURCE_ENABLE_POLYGON`
- `RESEARCH_SOURCE_ENABLE_SEC`
- `DISABLE_TRACING`
- optional `HTTP_PROXY`
- optional `HTTPS_PROXY`

## Current Engineering Notes

- The project now uses live company profile and market snapshot paths instead of mock-backed trader inputs.
- Trader outputs are normalized into a common schema for downstream reporting and validation.
- The validator is now part of the main pipeline.
- The system still depends on external APIs, so output quality depends on network stability and source availability.
- Some overlap across traders can still happen; validator is intended to detect when that overlap is justified versus lazy consensus.

## What GPT Should Assume In Future Sessions

- This is an LLM orchestration project, not a quant backtester.
- JSON contracts are important and should be preserved carefully.
- Changes in prompts, storage shape, or validator schema can break downstream interpretation.
- Avoid introducing mock data into normal production flow.
- Be careful with `.env`, secrets, and any API keys.

## Suggested Prompt Prefix For New Chats

Use this for future coding sessions:

```md
You are helping on `invest_agent_system`, a Python multi-agent investment research workflow.

Important project facts:
- Entrypoint: `app/main.py`
- Orchestrator: `app/runner.py`
- Pipeline: data collection -> signal extractor -> researcher -> value/growth/macro/event traders -> validator
- Agents: `app/agents/`
- Prompts: `app/prompts/`
- Sources: `app/sources/`
- Evidence tools: `app/tools/`
- Outputs: `app/data/runs/<run_id>/`

Important constraints:
- Preserve JSON schemas between steps
- Do not leak secrets from `.env`
- Prefer live SEC/Finnhub/Brave data paths over mock data
- Treat trader agents as investment underwriters, not generic information collectors
- Treat validator as a strict second-pass reviewer

Task:
[paste your task here]
```
