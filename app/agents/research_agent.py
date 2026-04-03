import json
from datetime import datetime
from typing import Any

from openai import AsyncOpenAI
from agents import Agent
from agents.models.openai_chatcompletions import OpenAIChatCompletionsModel

from app.config import settings
from app.prompts.research_prompt import RESEARCH_AGENT_PROMPT
from app.utils.agent_runner import run_agent_with_retry
from app.utils.trader_output import extract_json_dict


def build_research_agent(client: AsyncOpenAI) -> Agent:
    model = OpenAIChatCompletionsModel(
        model=settings.RESEARCH_MODEL,
        openai_client=client,
    )

    return Agent(
        name="Sector Strategist",
        model=model,
        instructions=RESEARCH_AGENT_PROMPT,
    )


def extract_json_from_text(text: str) -> dict[str, Any]:
    return extract_json_dict(text, "Researcher")


async def run_research_from_signals(
    signal_data: dict[str, Any],
    run_id: str,
    client: AsyncOpenAI,
) -> dict[str, Any]:
    agent = build_research_agent(client)

    input_data = json.dumps(signal_data, ensure_ascii=False, indent=2)
    result = await run_agent_with_retry(agent, input_data)
    parsed = extract_json_from_text(result.final_output)

    return {
        "run_id": run_id,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "agent_name": "researcher",
        "model": settings.RESEARCH_MODEL,
        "signal_input": signal_data,
        "raw_output": result.final_output,
        "candidate_sectors": parsed.get("candidate_sectors", []),
        "final_sectors": parsed.get("final_sectors", []),
        "summary": parsed.get("summary", ""),
    }
