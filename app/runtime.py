from __future__ import annotations

import os

from agents import set_default_openai_api, set_default_openai_client
from openai import AsyncOpenAI

from app.config import settings


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


def ensure_api_key() -> None:
    if not settings.OPENROUTER_API_KEY:
        raise ValueError("OPENROUTER_API_KEY 未设置，请先填写 .env 文件。")
