from dotenv import load_dotenv
load_dotenv()

import asyncio
import os

from openai import AsyncOpenAI
from agents import set_default_openai_api, set_default_openai_client

from app.config import settings
from app.runner import run_research_and_four_traders
from app.storage import create_run_id


def configure_client() -> AsyncOpenAI:
    client = AsyncOpenAI(
        api_key=settings.OPENROUTER_API_KEY,
        base_url=settings.OPENROUTER_BASE_URL,
        timeout=240.0,
        max_retries=5,
    )

    set_default_openai_client(client)
    set_default_openai_api("chat_completions")

    if settings.DISABLE_TRACING:
        os.environ["OPENAI_AGENTS_DISABLE_TRACING"] = "1"

    return client


async def main() -> None:
    if not settings.OPENROUTER_API_KEY:
        raise ValueError("OPENROUTER_API_KEY 未设置，请先填写 .env 文件。")

    client = configure_client()

    run_id = create_run_id()
    result_dirs = await run_research_and_four_traders(run_id=run_id, client=client)

    print("\n===== Workflow Completed =====")
    print(f"Run ID: {run_id}")
    print(f"Research saved to: {result_dirs['research_dir']}")
    print(f"Value Trader saved to: {result_dirs['value_dir']}")
    print(f"Growth Trader saved to: {result_dirs['growth_dir']}")
    print(f"Macro Trader saved to: {result_dirs['macro_dir']}")
    print(f"Event Trader saved to: {result_dirs['event_dir']}")
    print(f"Validator saved to: {result_dirs['validator_dir']}")


if __name__ == "__main__":
    asyncio.run(main())
