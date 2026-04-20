# Investment Agent System

A Python multi-agent investment research workflow that turns live market/news/SEC inputs into:

- sector theses from a researcher agent
- theme-aware candidate discovery before trader stock selection
- style-specific stock selections from value, growth, macro, and event traders
- a cross-checking validator review
- an interactive UI for full-run, industry-input, and single-stock workflows

Outputs are saved as structured JSON plus readable Markdown reports under `app/data/runs/<run_id>/`.

## What It Does

The pipeline simulates a buy-side research process:

1. Collect raw market/news/search/SEC inputs
2. Extract structured signals
3. Generate candidate and final sectors/themes
4. Discover and validate additional theme-relevant stocks
5. Build a shared evidence pack for all traders
6. Run four trader personas:
   - value / quality
   - growth
   - macro / regime
   - event / catalyst
7. Run a validator over all trader portfolios

Important portfolio-construction principle:

- the four traders do not need to produce fully disjoint portfolios
- shared picks are allowed when the evidence is strong
- but each shared pick must be justified through a different style-consistent thesis
- the validator should penalize duplicated reasoning more than simple overlap

The project supports three user-facing modes:

1. `Run whole procedure`
2. `Industry workflow`
3. `Single-stock workflow`

## Current Architecture

Entrypoints:

- `app/main.py`
- `streamlit_app.py`

Core orchestration:

- `app/runner.py`
- `app/runtime.py`

Main folders:

- `app/agents`
- `app/prompts`
- `app/sources`
- `app/tools`
- `app/utils`
- `app/data/runs`

## Data Sources

The system is designed to rely on live external data rather than mock data in normal operation.

Coverage target:

- U.S. listed stocks
- global industry leaders
- U.S.-listed ADRs and foreign issuers with usable live evidence paths

Current live source paths include:

- SEC submissions and company facts
- Finnhub quote, company profile, company news, and basic financial metrics
- Brave Search for thematic, IR, and transcript discovery

The system is no longer intended to be limited to U.S. domestic issuers only.
If a theme is better expressed by a global leader such as an ADR or foreign issuer with SEC/Finnhub coverage, that name should be eligible.

Trader agents are meant to behave as investment underwriters, not generic information collectors. Their arguments should be grounded in:

- `10-K / 10-Q / 8-K / DEF 14A` when available
- `20-F / 6-K / 40-F` for ADRs and foreign issuers when available
- filing-analysis excerpts
- IR materials and transcript links
- structured fundamentals
- market snapshot
- recent company-specific news and catalysts

## Candidate Discovery

The project now uses a two-layer stock universe approach:

1. Seed universe
   - built from `app/sources/universe_sources.py`
   - provides theme-to-ticker starting coverage

2. Candidate discovery
   - handled by `app/agents/candidate_discovery_agent.py`
   - expands the seed list with additional plausible tickers
   - only keeps tickers that pass live profile validation
   - now applies a theme-relevance gate so loosely related names are filtered before traders see them

The resulting theme ticker lists are attached to researcher output and then used by the traders.

## Style Differentiation Principle

This system does not aim to force all four trader agents into completely different names.

The real target is:

- style consistency within each trader
- differentiated reasoning across traders
- explicit justification when the same ticker appears in multiple portfolios

Examples of acceptable shared-pick differentiation:

- value: valuation support, balance-sheet quality, free-cash-flow durability, mean re-rating
- growth: adoption curve, TAM expansion, acceleration, earlier-stage upside runway
- macro: capex cycle, policy or infrastructure transmission, regime sensitivity
- event: concrete 3- to 6-month catalyst, guidance inflection, design win, re-rating trigger

Shared picks are acceptable.
Undifferentiated shared picks are not.

Important:

- the system is no longer intended to be limited to a hardcoded U.S.-only ticker map
- it supports global leaders and U.S.-listed ADRs where live evidence is strong enough
- it is still not a full global security master; coverage quality depends on seed mappings plus live validation

## Evidence Gate

The evidence pack builder now filters out names that are not sufficiently analysis-ready.

A stock is intended to reach the traders only if it has:

- live company profile coverage
- fundamentals or market snapshot support
- at least one meaningful supporting evidence path from filings, filing analysis, company news, or IR/transcript links

This is designed to reduce cases where a trader issues a judgment on a name with extremely weak live evidence.

## Run Flow

Current run sequence:

1. `STEP 1`: collect raw data
2. `STEP 2`: extract signals
3. `STEP 3`: generate sector ideas
4. `STEP 3.25`: discover candidate stocks
5. `STEP 3.5`: build shared evidence pack
6. `STEP 4`: value trader
7. `STEP 5`: growth trader
8. `STEP 6`: macro trader
9. `STEP 7`: event trader
10. `STEP 8`: validator

For manual-entry workflows:

- industry mode:
  - build an industry-focused research input
  - researcher analyzes the user-selected industry
  - candidate discovery expands the stock universe
  - traders select stocks from that industry research universe
  - validator cross-checks the outputs for both style fit and thesis differentiation

- stock mode:
  - build a direct evidence pack for the user-selected ticker
  - four traders analyze that exact stock from different styles
  - validator compares the style-specific judgments

## Outputs

Each run creates:

- `01_researcher`
- `02_trader_value`
- `03_trader_growth`
- `04_trader_macro`
- `05_trader_event`
- `06_validator`

Each step typically contains:

- `data.json`
- `report.md`

## Setup

### 1. Create and activate a virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Create your local env file

```bash
cp .env.example .env
```

Then fill in real values for:

- `OPENROUTER_API_KEY`
- `FINNHUB_API_KEY`
- `BRAVE_API_KEY`
- optionally `POLYGON_API_KEY`
- optionally `HTTP_PROXY` / `HTTPS_PROXY`

Do not commit `.env`.

### 4. Run the CLI pipeline

```bash
python -m app.main
```

### 5. Run the UI

```bash
python -m streamlit run streamlit_app.py
```

The UI exposes three entry points:

- `Run whole procedure`
- industry input -> researcher -> four traders -> validator
- single-stock input -> four traders -> validator

Each agent step is shown in the browser with both markdown and JSON views.

Important:

- Start Streamlit from the project virtual environment
- Prefer `python -m streamlit ...` instead of a globally installed `streamlit` command
- Otherwise the UI may start under Anaconda/system Python and fail to import project dependencies such as `openai`

Recommended startup:

```bash
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m streamlit run streamlit_app.py
```

## Environment Variables

See `.env.example` for the full template.

Most important settings:

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
- `SEC_USER_AGENT`

## Repository Hygiene

Before pushing to GitHub:

- keep `.env` local only
- do not commit API keys
- do not commit `.venv`
- do not commit `app/data/runs`
- do not commit `__pycache__`, `.pyc`, or `.DS_Store`

This repository includes a `.gitignore` for those defaults.

## Current Strengths

- live company profile and market snapshot paths are active
- trader outputs are normalized into a common schema
- validator is part of the main pipeline
- candidate discovery can now introduce global leaders and ADRs into the stock universe
- recent runs show names like `ASML` can now enter trader outputs

## Current Limitations

- the system is stronger for sectors with better seed-universe coverage and live evidence paths than for completely new sectors with weak seed coverage
- candidate discovery improves flexibility, but it can still surface lower-quality or style-misaligned names
- trader overlap can still be high on a small set of convincing names
- validator is good at flagging homogeneity, but trader differentiation still needs more work

## Notes

- This is an LLM workflow, not a backtesting engine.
- Output quality depends on both external data quality and prompt/schema discipline.
- If external APIs are unstable, the system attempts to degrade gracefully, but evidence quality may still weaken.
- Validator results should be reviewed critically; they are a second-pass reasoning layer, not a guarantee of correctness.
