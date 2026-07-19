from __future__ import annotations

import os
from typing import Literal

from agents import OpenAIChatCompletionsModel, set_tracing_disabled
from dotenv import load_dotenv
from openai import AsyncOpenAI


def create_agapi_client(base_url: str | None = None) -> AsyncOpenAI:
    """Create the OpenAI-compatible asynchronous AGAPI client."""
    load_dotenv(".env.cspilot")
    api_key = _require_env("AGAPI_API_KEY")
    resolved_base_url = base_url or _require_env("AGAPI_BASE_URL")
    return AsyncOpenAI(api_key=api_key, base_url=resolved_base_url)


def create_openrouter_client(base_url: str | None = None) -> AsyncOpenAI:
    """Create the OpenAI-compatible asynchronous OpenRouter client."""
    load_dotenv(".env.cspilot")
    api_key = _require_env("OPENROUTER_API_KEY")
    resolved_base_url = base_url or os.getenv(
        "OPENROUTER_BASE_URL",
        "https://openrouter.ai/api/v1",
    )
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


def openrouter_configured() -> bool:
    """Return true when OpenRouter fallback has enough configuration to run."""
    load_dotenv(".env.cspilot")
    return bool(os.getenv("OPENROUTER_API_KEY"))


def should_fallback_to_openrouter(exc: Exception) -> bool:
    """Return true for common AGAPI model/backend failures."""
    text = f"{type(exc).__name__}: {exc}".lower()
    fallback_tokens = (
        "model not found",
        "model_not_found",
        "invalid model",
        "not found",
        "404",
        "bad request",
        "connection",
        "timeout",
        "temporarily unavailable",
        "missing required environment variable",
    )
    return openrouter_configured() and any(token in text for token in fallback_tokens)


LLMProvider = Literal["auto", "openrouter", "agapi"]


def resolve_llm_provider(
    profile: str = "chem",
    requested: LLMProvider = "auto",
) -> Literal["openrouter", "agapi"]:
    """Resolve the model backend for planner/agent calls.

    OpenRouter is the default while AGAPI model serving is unstable. AGAPI can
    still be selected explicitly with CLI flags, and AGAPI/JARVIS materials
    tools remain separate deterministic tool calls.
    """
    if requested in {"openrouter", "agapi"}:
        return requested

    env_provider = os.getenv("CSPILOT_LLM_PROVIDER", "").strip().lower()
    if env_provider in {"openrouter", "agapi"}:
        return env_provider  # type: ignore[return-value]

    return "openrouter"


def create_llm_model(
    provider: LLMProvider = "auto",
    profile: str = "chem",
    model: str | None = None,
    base_url: str | None = None,
) -> OpenAIChatCompletionsModel:
    """Create the configured OpenAI-compatible model backend."""
    selected = resolve_llm_provider(profile=profile, requested=provider)
    if selected == "openrouter":
        return create_openrouter_model(model=model, base_url=base_url)
    return create_agapi_model(model=model, base_url=base_url)


def _require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise ValueError(f"Missing required environment variable: {name}")
    return value
