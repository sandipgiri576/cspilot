from __future__ import annotations

import os

from agents import OpenAIChatCompletionsModel, set_tracing_disabled
from dotenv import load_dotenv
from openai import AsyncOpenAI


def create_agapi_client(base_url: str | None = None) -> AsyncOpenAI:
    """Create the OpenAI-compatible asynchronous AGAPI client."""
    load_dotenv(".env.cspilot")
    api_key = _require_env("AGAPI_API_KEY")
    resolved_base_url = base_url or _require_env("AGAPI_BASE_URL")
    return AsyncOpenAI(api_key=api_key, base_url=resolved_base_url)


def create_agapi_model(
    model: str | None = None,
    base_url: str | None = None,
) -> OpenAIChatCompletionsModel:
    """Create an Agents SDK chat completions model backed by AGAPI."""
    load_dotenv(".env.cspilot")
    set_tracing_disabled(disabled=True)
    return OpenAIChatCompletionsModel(
        model=model or _require_env("cspilot_MODEL"),
        openai_client=create_agapi_client(base_url=base_url),
    )


def _require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise ValueError(f"Missing required environment variable: {name}")
    return value
