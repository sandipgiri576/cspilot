from __future__ import annotations

import os

from agents import OpenAIChatCompletionsModel, set_tracing_disabled
from dotenv import load_dotenv
from openai import AsyncOpenAI


def create_openrouter_client(base_url: str | None = None) -> AsyncOpenAI:
    """Create the OpenAI-compatible asynchronous OpenRouter client."""
    load_dotenv(".env.cspilot")
    api_key = _require_env("OPENROUTER_API_KEY")
    resolved_base_url = base_url or os.getenv(
        "OPENROUTER_BASE_URL",
        "https://openrouter.ai/api/v1",
    )
    return AsyncOpenAI(api_key=api_key, base_url=resolved_base_url, timeout=60.0, max_retries=1)


def create_openrouter_model(
    model: str | None = None,
    base_url: str | None = None,
) -> OpenAIChatCompletionsModel:
    """Create an Agents SDK chat completions model backed by OpenRouter."""
    load_dotenv(".env.cspilot")
    set_tracing_disabled(disabled=True)
    return OpenAIChatCompletionsModel(
        model=model or os.getenv("OPENROUTER_MODEL", "openai/gpt-oss-20b:free"),
        openai_client=create_openrouter_client(base_url=base_url),
    )


def create_llm_model(
    model: str | None = None,
    base_url: str | None = None,
) -> OpenAIChatCompletionsModel:
    """Create the OpenRouter-backed model used by all model calls."""
    return create_openrouter_model(model=model, base_url=base_url)


def _require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise ValueError(f"Missing required environment variable: {name}")
    return value
