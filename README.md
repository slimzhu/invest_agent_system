# Investment Agent System

A Python multi-agent investment research workflow that turns market/news/SEC inputs into:

- sector theses from a researcher agent
- style-specific stock selections from value, growth, macro, and event traders
- a cross-checking validator review
- an interactive UI for full-run, industry-input, and single-stock workflows

Outputs are saved as structured JSON plus readable Markdown reports under `app/data/runs/<run_id>/`.

## What It Does

The pipeline simulates a buy-side research process:

1. Collect raw market/news/search/SEC inputs
2. Extract structured signals
3. Generate candidate and final sectors/themes
4. Build a shared evidence pack for all traders
5. Run four trader personas:
   - value / quality
   - growth
   - macro / regime
   - event / catalyst
6. Run a validator over all trader portfolios

The project now supports three user-facing modes:

1. `Run whole procedure`
2. `Industry workflow`
3. `Single-stock workflow`

## Current Architecture

Entrypoint:

- `app/main.py`
- `streamlit_app.py`

Core orchestration:

- `app/runner.py`

Main folders:

- `app/agents`
- `app/prompts`
- `app/sources`
- `app/tools`
- `app/utils`
- `app/data/runs`

Main runtime helpers:

- `app/runner.py`
- `app/runtime.py`

## Data Sources

The system is designed to rely on live external data rather than mock data in normal operation.

Current live source paths include:

- SEC submissions and company facts
- Finnhub quote, company profile, company news, and basic financial metrics
- Brave Search for thematic, IR, and transcript discovery

Trader agents are meant to behave as investment underwriters, not generic information collectors. Their arguments should be grounded in:

- 10-K / 10-Q / 8-K / DEF 14A when available
- filing-analysis excerpts
- IR materials and transcript links
- structured fundamentals
- market snapshot
- recent company-specific news and catalysts

## Run Flow

Current run sequence:

1. `STEP 1`: collect raw data
2. `STEP 2`: extract signals
3. `STEP 3`: generate sector ideas
4. `STEP 3.5`: build shared evidence pack
5. `STEP 4`: value trader
6. `STEP 5`: growth trader
7. `STEP 6`: macro trader
8. `STEP 7`: event trader
9. `STEP 8`: validator

For manual-entry workflows:

- industry mode:
  - build an industry-focused research input
  - researcher analyzes the user-selected industry
  - traders select stocks from that industry research universe
  - validator cross-checks the outputs

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

This repository now includes a `.gitignore` for those defaults.

## Notes

- This is an LLM workflow, not a backtesting engine.
- Output quality depends on both external data quality and prompt/schema discipline.
- If external APIs are unstable, the system attempts to degrade gracefully, but evidence quality may still weaken.
- Validator results should be reviewed critically; they are a second-pass reasoning layer, not a guarantee of correctness.
