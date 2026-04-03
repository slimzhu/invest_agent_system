import json
from datetime import datetime
from typing import Any

from openai import AsyncOpenAI
from agents import Agent, Runner
from agents.models.openai_chatcompletions import OpenAIChatCompletionsModel

from app.config import settings
from app.utils.agent_runner import run_agent_with_retry


RESEARCH_SIGNAL_PROMPT = """
You are a buy-side research signal extractor.

Your job is to convert raw source inputs into structured investable signals.

You will receive:
- macro news
- thematic search results
- company news signals
- social signal results
- SEC validation samples

Rules:
- Extract themes, not stock picks
- Remove noise and repetition
- Prefer forward-looking insights
- Social signals = early alpha hints
- Company + SEC = higher reliability

Return exactly ONE JSON object.

Output format:

{
  "macro_regime": {
    "summary": "Short paragraph",
    "key_flags": ["flag1", "flag2"]
  },
  "theme_signals": [
    {
      "theme": "AI infrastructure",
      "insight": "Short paragraph",
      "source_types": ["company_news", "search"],
      "strength": "high"
    }
  ],
  "social_signals": [
    {
      "theme": "Optical networking",
      "insight": "Short paragraph",
      "strength": "medium"
    }
  ],
  "noise": [
    "irrelevant signal example"
  ]
}

Do not include markdown fences.
Do not include extra text.
"""


def build_signal_agent(client: AsyncOpenAI) -> Agent:
    model = OpenAIChatCompletionsModel(
        model=settings.RESEARCH_MODEL,
        openai_client=client,
    )

    return Agent(
        name="Signal Extractor",
        model=model,
        instructions=RESEARCH_SIGNAL_PROMPT,
    )


def extract_json(text: str) -> dict[str, Any]:
    text = text.strip()

    try:
        return json.loads(text)
    except Exception:
        pass

    decoder = json.JSONDecoder()
    for i, ch in enumerate(text):
        if ch != "{":
            continue
        try:
            obj, _ = decoder.raw_decode(text[i:])
            return obj
        except Exception:
            continue

    raise ValueError("Signal JSON parse failed")


async def run_signal_extractor(input_data: str, run_id: str, client: AsyncOpenAI) -> dict[str, Any]:
    agent = build_signal_agent(client)

    result = await run_agent_with_retry(agent, input_data)
    parsed = extract_json(result.final_output)

    return {
        "run_id": run_id,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "agent_name": "research_signal_extractor",
        "model": settings.RESEARCH_MODEL,
        "raw_output": result.final_output,
        "macro_regime": parsed.get("macro_regime", {}),
        "theme_signals": parsed.get("theme_signals", []),
        "social_signals": parsed.get("social_signals", []),
        "noise": parsed.get("noise", []),
    }
