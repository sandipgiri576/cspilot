from __future__ import annotations

import asyncio
from types import SimpleNamespace

from cspilot import llm
from cspilot.agents import openai_agent, planner
from cspilot.agents.planner import ExecutionPlan


def test_create_openrouter_model_uses_openrouter_defaults(monkeypatch, tmp_path):
    captured = {}

    class FakeModel:
        def __init__(self, model, openai_client):
            captured["model"] = model
            captured["client"] = openai_client

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("OPENROUTER_API_KEY", "or-key")
    monkeypatch.delenv("OPENROUTER_MODEL", raising=False)
    monkeypatch.setattr(llm, "OpenAIChatCompletionsModel", FakeModel)

    model = llm.create_openrouter_model()

    assert isinstance(model, FakeModel)
    assert captured["model"] == "openai/gpt-oss-20b:free"
    assert str(captured["client"].base_url) == "https://openrouter.ai/api/v1/"


def test_planner_uses_openrouter_by_default(monkeypatch):
    calls = []

    async def fake_run(user_request, instructions, model):
        calls.append(model)
        return SimpleNamespace(final_output=ExecutionPlan(steps=[]))

    monkeypatch.setenv("OPENROUTER_API_KEY", "or-key")
    monkeypatch.setattr(
        planner,
        "create_llm_model",
        lambda model=None, base_url=None: "openrouter-model",
    )
    monkeypatch.setattr(planner, "_run_planner_agent", fake_run)

    plan = asyncio.run(planner.create_plan("inspect water", profile="chem"))

    assert plan == {"steps": []}
    assert calls == ["openrouter-model"]


def test_direct_agent_uses_openrouter_by_default(monkeypatch, tmp_path):
    calls = []

    async def fake_runner_run(agent, request):
        calls.append(agent.model)
        return SimpleNamespace(final_output="done", new_items=[])

    monkeypatch.setenv("OPENROUTER_API_KEY", "or-key")
    monkeypatch.setattr(
        openai_agent,
        "create_llm_model",
        lambda model=None, base_url=None: "openrouter-model",
    )
    monkeypatch.setattr(openai_agent.Runner, "run", fake_runner_run)

    result = asyncio.run(
        openai_agent.run_agent_request("hello", tmp_path, profile="general")
    )

    assert calls == ["openrouter-model"]
    assert result["model_provider"] == "openrouter"
    assert result["model_output"] == "done"
