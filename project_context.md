# Project Context

## One-line Summary

`invest_agent_system` is a Python multi-agent investment research workflow that collects live market/SEC/search data, produces sector theses, expands stock candidates, runs four style-specific trader agents, and then runs a validator over the combined portfolio outputs.

## Goal

The system is designed to simulate a buy-side idea generation process:

1. collect raw external signals
2. extract structured investment signals
3. generate candidate and final sectors
4. expand the stock universe beyond a narrow seed list
5. let multiple trader styles argue for stock picks
6. validate the final portfolio set with a second-pass reviewer

Primary output types:

- `BUY`
- `WATCH`
- `SELL`

Coverage target:

- U.S. listed stocks
- global leaders
- U.S.-listed ADRs / foreign issuers where evidence quality is sufficient

Important non-goal:

- this is not a full global security master or institutional market data platform
- coverage is strongest where theme seed mappings and live evidence paths are both available

## Current End-to-End Flow

Entrypoints:

- `app/main.py`
- `streamlit_app.py`

Orchestration:

- `app/runner.py`
- `app/runtime.py`

Current runtime order:

1. `STEP 1`: collect raw data
2. `STEP 2`: signal extractor
3. `STEP 3`: researcher / sector strategist
4. `STEP 3.25`: candidate discovery / stock universe expansion
5. `STEP 3.5`: build shared evidence pack
6. `STEP 4`: value trader
7. `STEP 5`: growth trader
8. `STEP 6`: macro trader
9. `STEP 7`: event trader
10. `STEP 8`: validator

## Entry Modes

The project supports three user-facing entry modes:

1. `Run whole procedure`
   - full default pipeline
   - raw data -> signal extractor -> researcher -> candidate discovery -> traders -> validator

2. `Industry workflow`
   - user manually enters an industry or theme
   - system builds an industry-focused research input
   - researcher analyzes the industry
   - candidate discovery expands the stock universe
   - four traders pick stocks from that research universe
   - validator reviews the combined output for both style fit and thesis differentiation

3. `Stock workflow`
   - user manually enters a ticker
   - system builds a direct single-stock evidence context
   - four traders analyze that exact stock only from different styles
   - validator compares the four style-specific judgments
   - this mode does not depend on the default researcher-first discovery path

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

### `candidate_discovery_agent.py`

Expands the theme stock universe after researcher output and before trader stock selection.

Typical output:

- per-theme `validated_tickers`
- candidate expansion rationale

Purpose:

- reduce dependence on a narrow hardcoded universe
- allow global leaders and ADRs to enter the candidate pool
- still require live validation before traders see a name

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
- penalize homogeneity and style drift
- allow shared picks when the theses are meaningfully different and style-faithful

## Data Philosophy

This project should use **live data paths**, not mock data, in normal operation.

Important principles:

- trader agents are not information collectors
- trader agents are investment underwriters / thesis builders
- if evidence quality is too weak, the stock should be filtered or downgraded rather than forced into a confident judgment

So trader reasoning should be grounded in:

- `10-K / 10-Q / 8-K / DEF 14A` when available
- `20-F / 6-K / 40-F` for ADRs / foreign issuers when available
- filing analysis excerpts
- IR presentation / transcript / webcast links
- structured fundamentals
- valuation and market data
- recent company-specific news
- near-term and medium-term catalysts

The system should not be artificially constrained to U.S. domestic issuers if a global leader or ADR is the cleaner expression of the theme.

## Style Consistency Rule

The project does not require the four trader agents to produce fully disjoint portfolios.

Correct target behavior:

- some overlap is acceptable when a stock is genuinely compelling
- each trader must justify the stock through its own style mandate
- the same ticker should not be selected with copy-paste logic across styles

Examples of acceptable differentiation:

- value: valuation support, free cash flow durability, balance-sheet quality, mean re-rating
- growth: accelerating demand, TAM expansion, product cycle, earlier adoption curve
- macro: capex cycle, policy tailwind, infrastructure transmission, regime sensitivity
- event: concrete 3- to 6-month catalyst, guidance inflection, design win, near-term re-rating trigger

Validator philosophy:

- penalize duplicated reasoning more than simple overlap
- penalize style drift when a thesis clearly belongs to another style
- do not penalize overlap when the shared ticker has clearly differentiated and style-consistent theses

## Main Data Sources

### SEC

Used for:

- company submissions
- company facts
- recent filings
- filing analysis

Important forms:

- domestic issuers: `10-K`, `10-Q`, `8-K`, `DEF 14A`
- ADR / foreign issuers: `20-F`, `6-K`, `40-F`

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

## Universe Construction

Universe construction is now hybrid, not purely hardcoded.

Layer 1: seed universe

- file: `app/sources/universe_sources.py`
- maps common sector/theme strings to starter ticker lists

Layer 2: candidate discovery

- file: `app/agents/candidate_discovery_agent.py`
- prompt: `app/prompts/candidate_discovery_prompt.py`
- expands per-theme candidates beyond the seed list
- validates proposed tickers through live company profile checks
- applies a theme-relevance score so adjacent but weakly related names are filtered out

Layer 3: evidence gate

- file: `app/tools/evidence_pack_builder.py`
- removes names that are not sufficiently analysis-ready

Current analysis-ready logic expects:

- live company profile coverage
- fundamentals or market snapshot support
- at least one support path from filings / filing analysis / news / IR materials

## Shared Evidence Pack

The system builds a shared evidence pack before the traders run, so the four traders do not each re-fetch the same external data from scratch.

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

Important implementation detail:

- the evidence pack can exclude stocks that fail minimum evidence thresholds
- excluded names are tracked in `excluded_by_theme`

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
- `app/runtime.py`
- `app/runner.py`
- `app/config.py`
- `app/storage.py`
- `streamlit_app.py`
- `app/agents/*.py`
- `app/prompts/*.py`
- `app/sources/*.py`
- `app/tools/*.py`
- `app/utils/*.py`

Most important files for the current stock-selection logic:

- `app/runner.py`
- `app/agents/candidate_discovery_agent.py`
- `app/prompts/candidate_discovery_prompt.py`
- `app/sources/universe_sources.py`
- `app/tools/evidence_pack_builder.py`
- `app/tools/filings_collector.py`
- `app/tools/filing_parser.py`

## UI

The project has a lightweight Streamlit UI:

- file: `streamlit_app.py`
- recommended command: `python -m streamlit run streamlit_app.py`

The UI shows:

- the existing `Run whole procedure` button
- an industry input workflow
- a single-stock input workflow
- every agent output in markdown + JSON form

Important runtime note:

- launch Streamlit from the project `.venv`
- do not rely on a global Anaconda/system `streamlit` binary
- otherwise imports like `openai` may fail even if the project virtualenv is configured correctly

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
- The validator is part of the main pipeline.
- The system still depends on external APIs, so output quality depends on network stability and source availability.
- Candidate discovery is active, but it can still produce theme-expansion names that are directionally plausible yet not always the best style-specific picks.
- Semiconductor coverage is currently more mature than many other sectors because seed mappings and prompt tuning have been expanded there first.

Recent observed behavior from current runs:

- global names such as `ASML` can now enter trader outputs
- discovery can surface additional names such as `TER`, `ENTG`, `CDNS`, `SNPS`, `MRVL`, `ON`, `SWKS`, `QRVO`, `INDI`, `AEHR`
- overlap can still remain high on names like `LRCX`, `MRVL`, and `CDNS`
- validator can now downgrade the combined portfolio to `watchlist` when homogeneity is too high

Known next-step themes for future work:

- broader industry taxonomy beyond semiconductors
- better ranking/prioritization inside candidate discovery
- stronger trader differentiation to reduce overlap
- stricter handling of evidence weakness for foreign issuers with partial coverage

## What GPT Should Assume In Future Sessions

- This is an LLM orchestration project, not a quant backtester.
- JSON contracts are important and should be preserved carefully.
- Changes in prompts, storage shape, or validator schema can break downstream interpretation.
- Avoid introducing mock data into normal production flow.
- Be careful with `.env`, secrets, and any API keys.
- The current architecture is:
  - research signal extraction
  - researcher sector selection
  - candidate discovery
  - live validation / evidence gate
  - four trader styles
  - validator
- The project supports:
  - full workflow
  - industry workflow
  - single-stock workflow
- The system is intended to support:
  - U.S. listed stocks
  - global leaders
  - U.S.-listed ADRs
  but not arbitrary non-U.S. local listings with no evidence path

## Suggested Prompt Prefix For New Chats

Use this for future coding sessions:

```md
You are helping on `invest_agent_system`, a Python multi-agent investment research workflow.

Important project facts:
- Entrypoint: `app/main.py`
- Orchestrator: `app/runner.py`
- UI: `streamlit_app.py`
- Pipeline: data collection -> signal extractor -> researcher -> candidate discovery -> evidence gate -> value/growth/macro/event traders -> validator
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
- Support global leaders and U.S.-listed ADRs when evidence quality is sufficient
- Be aware that candidate discovery and theme seed mappings both affect final stock selection
- Avoid forcing confident judgments on names with weak evidence coverage

Current known realities:
- semiconductor coverage is currently ahead of many other sectors
- candidate discovery is active but still needs better ranking quality
- trader overlap can still be too high and validator is expected to call that out

Task:
[paste your task here]
```
