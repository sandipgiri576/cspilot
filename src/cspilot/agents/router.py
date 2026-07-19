from __future__ import annotations

from typing import Any

from cspilot.prompts.system_prompts import get_profile

SPECIALISTS = ("chem", "stk", "materials", "analysis", "thermo", "general")


def route_request(user_request: str, profile: str = "auto") -> dict[str, Any]:
    """Route a request to one deterministic specialist profile."""
    requested = profile.lower().strip()
    if requested != "auto":
        specialist = requested if requested in SPECIALISTS else "general"
        selected = get_profile(specialist)
        return {
            "success": True,
            "specialist": specialist,
            "reason": f"Explicit profile '{profile}' was requested.",
            "allowed_tool_groups": list(selected.allowed_tool_groups),
        }

    lowered = user_request.lower()
    routes = [
        (
            "stk",
            ("stk", "build", "construct", "cage", "polymer", "topology", "edit", "replace group"),
            "Request mentions stk-style molecule construction or editing.",
        ),
        (
            "thermo",
            ("heat of combustion", "nhoc", "combustion", "enthalpy", "thermochemistry"),
            "Request asks for thermochemistry or reaction-energy reporting.",
        ),
        (
            "analysis",
            ("extract", "parse", "result", "json", "gibbs", "homo", "lumo", "gap", "frequency", "multiwfn"),
            "Request asks to inspect or extract stored calculation results.",
        ),
        (
            "materials",
            ("material", "materials", "jarvis", "al2o3", "crystal", "formation energy", "band gap database"),
            "Request asks for materials or crystal search.",
        ),
        (
            "chem",
            ("xtb", "orca", "mace", "ase", "optimize", "optimise", "frequency", "single point", "sp calculation"),
            "Request asks for a computational chemistry calculation.",
        ),
    ]
    for specialist, keywords, reason in routes:
        if any(keyword in lowered for keyword in keywords):
            selected = get_profile(specialist)
            return {
                "success": True,
                "specialist": specialist,
                "reason": reason,
                "allowed_tool_groups": list(selected.allowed_tool_groups),
            }

    selected = get_profile("chem")
    return {
        "success": True,
        "specialist": "chem",
        "reason": "No specialist keywords were detected; defaulting to chemistry.",
        "allowed_tool_groups": list(selected.allowed_tool_groups),
    }
